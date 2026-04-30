"""
Upstox WebSocket Live Data Stream (V3 SDK)
Real-time market data feed from Upstox API using Official V3 Streamer.
"""
import asyncio
import logging
import threading
from datetime import datetime, time
from typing import Dict, Optional, Callable, List
from dataclasses import dataclass

# Upstox V3 SDK Imports
import upstox_client
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3
from upstox_client.feeder.streamer import Streamer

from core.config_manager import sys_config
from core.event_bus import bus, EventType
from core.greeks import GreeksCalculator

import logging
import http.client
http.client.HTTPConnection.debuglevel = 1

logger = logging.getLogger(__name__)

# Debug Logging for Websockets
logging.getLogger('websockets').setLevel(logging.DEBUG)
logging.getLogger('upstox_client').setLevel(logging.DEBUG)


@dataclass
class Tick:
    """Single market tick."""
    symbol: str
    ltp: float  # Last Traded Price
    open: float
    high: float
    low: float
    close: float  # Previous close
    volume: int
    bid: float
    ask: float
    timestamp: datetime
    change: float = 0.0
    change_percent: float = 0.0
    # Greeks
    delta: float = 0.0
    theta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    iv: float = 0.0

class UpstoxWebSocket:
    """
    Upstox WebSocket connection wrapper for V3 SDK Streamer.
    Runs the synchronous Streamer in a separate thread.
    """
    
    def __init__(self):
        self.access_token = sys_config.ACCESS_TOKEN
        self.streamer: Optional[MarketDataStreamerV3] = None
        self.is_connected = False
        self.subscribed_instruments: set[str] = set()
        
        # Callbacks
        self.on_tick: Optional[Callable] = None
        
        # Candle aggregation
        self.candle_data: Dict[str, Dict] = {}
        
        # Market status
        self.is_market_open = False
        
        # Greeks Engine
        self.greeks_calc = GreeksCalculator()
        self.nifty_spot = 23500.0  # Default fallback
        self.banknifty_spot = 50000.0
        
        self.loop = None
        
        # Initialize Streamer
        self._setup_streamer()

    def _setup_streamer(self):
        """Initialize the V3 Streamer."""
        if not self.access_token:
            logger.warning("No access token. Streamer cannot start.")
            return

        try:
            config = upstox_client.Configuration()
            config.access_token = self.access_token
            api_client = upstox_client.ApiClient(config)
            
            # Initialize V3 Streamer
            self.streamer = MarketDataStreamerV3(api_client, [], "full")
            
            # Set Callbacks
            self.streamer.on("open", self._on_open)
            self.streamer.on("message", self._on_message)
            self.streamer.on("error", self._on_error)
            self.streamer.on("close", self._on_close)
            
            logger.info("Upstox V3 Streamer Initialized")
        except Exception as e:
            logger.error(f"Failed to setup streamer: {e}")

    def _check_market_hours(self) -> bool:
        """Check if Indian market is open."""
        now = datetime.now()
        if now.weekday() >= 5: return False
        market_open = time(9, 15)
        market_close = time(15, 30)
        return market_open <= now.time() <= market_close
    
    async def connect(self):
        """Start the Streamer in a background thread."""
        if not self.streamer:
            logger.warning("Streamer not initialized, skipping connect.")
            return

        if self.is_connected:
            return

        # Capture correct running loop
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("No running loop found in connect(), using get_event_loop()")
            self.loop = asyncio.get_event_loop()

        logger.info("Starting Upstox Streamer Thread...")
        
        # Run in thread (connect is blocking) - No args supported in this version
        self.streamer_thread = threading.Thread(target=self.streamer.connect, daemon=True)
        self.streamer_thread.start()
        
    async def subscribe(self, keys: List[str]):
        """Subscribe to instruments."""
        logger.info(f"Requesting Subscription for: {keys} | Connected: {self.is_connected}")
        if not self.streamer: 
             logger.warning("Streamer is None in subscribe")
             return
        
        # Convert to list if single str
        if isinstance(keys, str): keys = [keys]
        
        new_keys = []
        for k in keys:
             if k not in self.subscribed_instruments:
                 new_keys.append(k)
                 self.subscribed_instruments.add(k)
        
        logger.info(f"New Keys to Add: {new_keys}")
        
        if new_keys:
             if self.is_connected:
                 try:
                     # Run blocking SDK subscribe in executor
                     if not self.loop: self.loop = asyncio.get_running_loop()
                     await self.loop.run_in_executor(None, lambda: self.streamer.subscribe(new_keys, "full"))
                     logger.info(f"Subscribed to: {new_keys}")
                 except Exception as e:
                     logger.error(f"SDK Subscribe Error: {e}")
             else:
                 logger.warning("Not connected yet, keys queued.")
    
    # --- SDK Callbacks (Run in Thread) ---
    
    def _on_open(self):
        """Called when WebSocket opens."""
        self.is_connected = True
        logger.info("✅ Upstox V3 Streamer Connected")
        
        # Publish generic event
        future = asyncio.run_coroutine_threadsafe(
             bus.publish(EventType.SYSTEM_STATUS, {'status': 'connected', 'source': 'upstox'}),
             self.loop
        )
        
        
        # Resubscribe if we have pending keys
        if self.subscribed_instruments:
             self.streamer.subscribe(list(self.subscribed_instruments), "full")

    def _on_close(self, *args):
        """Called when WebSocket closes."""
        self.is_connected = False
        logger.warning(f"Upstox Streamer Closed: {args}")
        # Notify Bus
        if self.loop and not self.loop.is_closed():
             future = asyncio.run_coroutine_threadsafe(
                 bus.publish(EventType.SYSTEM_STATUS, {'status': 'disconnected', 'source': 'upstox'}),
                 self.loop
             )

    def _on_error(self, error):
        logger.error(f"Streamer Error: {error}")

    def _on_message(self, data):
        """
        Called when market data is received.
        Data is already decoded by SDK into python objects.
        """
        try:
             # logger.info(f"raw_msg_type: {type(data)}") # Debug Type
             # logger.debug(f"Row: {str(data)[:50]}...")
             # print(f"RAW_STREAM_MSG: {str(data)[:100]}") # REDUCED LOGGING
             
             if self.loop and not self.loop.is_closed():
                 self.loop.call_soon_threadsafe(self._process_feed_sync, data)
             else:
                 logger.error("Event Loop Closed or None")
        except Exception as e:
             logger.error(f"Error handling message: {e}")

    def _process_feed_sync(self, feeds):
        """Async bridge: Process feed data in the event loop."""
        # logger.info(f"Processing Feed: {len(feeds)} items") 
        asyncio.create_task(self._process_feed(feeds))

    async def _process_feed(self, message: Dict):
        """Process decoded feed data."""
        # Message format: { 'type': 'live_feed', 'feeds': { 'NSE_INDEX|Nifty 50': {...} } }
        # OR initial snapshot: { 'feeds': { ... } }
        # Extract the actual feeds dict
        
        feeds = message.get('feeds', message)  # Unwrap if wrapped, else use as-is
        
        # Skip non-feed messages like market_info
        if not isinstance(feeds, dict):
            return
        
        # Skip if this is actually the wrapper itself and has 'type' but no real feeds
        if 'type' in feeds and 'feeds' not in message:
            return  # This was a market_info or similar, skip
        
        for symbol, feed_data in feeds.items():
            # Skip non-symbol keys like 'type', 'currentTs'
            if symbol in ('type', 'currentTs', 'marketInfo'):
                continue
            
            ltp = 0.0
            open_p = 0.0
            high = 0.0
            low = 0.0
            close = 0.0
            volume = 0
            
            try:
                # Based on standard usage, feed_data is an object with 'ltpc', 'ohlc' etc attributes
                # But sometimes it acts like a dict in flexible python
                
                # Helper to get attr or item
                def get_val(obj, key, default=None):
                    if hasattr(obj, key): return getattr(obj, key)
                    if isinstance(obj, dict): return obj.get(key, default)
                    return default
                
                # --- DRILL DOWN TO LTPC ---
                # Structure: { fullFeed: { indexFF: { ltpc: ... } } }
                
                # 1. Get Full wrapped
                ff = get_val(feed_data, 'fullFeed', None)
                if not ff: ff = get_val(feed_data, 'ff', None) # Alias?
                
                target_node = feed_data # Default to root if flatten
                
                if ff:
                    # 2. Get Segment (indexFF or liveFF)
                    # Indices use indexFF, Stocks use liveFF(?) or marketFF
                    index_ff = get_val(ff, 'indexFF', None)
                    market_ff = get_val(ff, 'marketFF', None)
                    live_ff = get_val(ff, 'liveFF', None) # Backup
                    
                    if index_ff: target_node = index_ff
                    elif market_ff: target_node = market_ff
                    elif live_ff: target_node = live_ff
                    else:
                        # Fallback: check keys
                        if isinstance(ff, dict):
                             # Take first value?
                             keys = list(ff.keys())
                             if keys: target_node = ff[keys[0]]
                
                # NOW Extract LTPC from target_node
                ltpc = get_val(target_node, 'ltpc', None)
                if ltpc:
                    ltp = get_val(ltpc, 'ltp', 0.0)
                    close = get_val(ltpc, 'cp', 0.0)
                    volume = get_val(ltpc, 'vol', 0)
                    if volume == 0: volume = get_val(ltpc, 'v', 0)

                # OHLC
                ohlc = get_val(target_node, 'marketOHLC', None) # V3 often puts it here
                if not ohlc: ohlc = get_val(target_node, 'ohlc', None)
                
                if ohlc:
                     # Often OHLC is a list of candles or single object 'ohlc'
                     # Based on log: 'marketOHLC': {'ohlc': [ ... ]}
                     inner_ohlc = get_val(ohlc, 'ohlc', [])
                     if isinstance(inner_ohlc, list) and inner_ohlc:
                         # Use I1 (1 min) or relevant. Usually last item is latest?
                         # Log shows: [{'interval': '1d', ...}, {'interval': 'I1', ...}]
                         # We want the daily or latest candle for OHLC context
                         latest = inner_ohlc[-1] # Assume last is latest
                         open_p = get_val(latest, 'open', 0.0)
                         high = get_val(latest, 'high', 0.0)
                         low = get_val(latest, 'low', 0.0)
                         if close == 0: close = get_val(latest, 'close', 0.0)

            except Exception as e:
                logger.error(f"Parsing error for {symbol}: {e}")
                pass
            
            if ltp == 0: continue
            
            # --- DEBUGGING LTP ---
            if "Nifty 50" in symbol or "Nifty Bank" in symbol:
                print(f"DEBUG_TICK: {symbol} LTP={ltp} Time={datetime.now().time()}")
            # ---------------------

            # --- Update Spot Prices ---
            if "Nifty 50" in symbol: self.nifty_spot = ltp
            elif "Nifty Bank" in symbol: self.banknifty_spot = ltp
            
            # Create Tick
            tick = Tick(
                symbol=symbol,
                ltp=ltp,
                open=open_p, high=high, low=low, close=close,
                volume=volume,
                bid=0.0, ask=0.0,
                timestamp=datetime.now()
            )
            
            # Change
            if tick.close > 0:
                tick.change = tick.ltp - tick.close
                tick.change_percent = (tick.change / tick.close) * 100
            
            # Greeks (Option Only)
            if "NSE_FO" in symbol:
                self._calculate_greeks(tick)
            
            # Emit Tick
            await bus.publish(EventType.TICK, {
                'symbol': tick.symbol,
                'ltp': tick.ltp,
                'change': tick.change,
                'change_percent': tick.change_percent,
                'timestamp': tick.timestamp.isoformat(), # ISO format for JS
                'delta': tick.delta,
                'iv': tick.iv
            })
            
            # Callback
            if self.on_tick:
                await self.on_tick(tick)
            
            # Aggregate Candle
            await self._aggregate_candle(tick)
            
    def _calculate_greeks(self, tick: Tick):
        try:
             import re
             # Parse Symbol: NSE_FO|NIFTY23500CE (Typical)
             # Adjust regex if needed:
             # NIFTY23500CE might be part of instrument key "NSE_FO|54242"
             # Actually, symbol passed here is the Instrument Key (e.g. NSE_INDEX|Nifty 50)
             # If it is a token, we can't parse strike easily without map.
             # Assuming keys are human readable if subscribed as such, OR we need a lookup.
             # For MVP, if key involves string "CE" or "PE", parse it.
             
             match = re.search(r'(NIFTY|BANKNIFTY).*?(\d{5}).*?(CE|PE)', tick.symbol, re.IGNORECASE)
             if match:
                 index = match.group(1).upper()
                 strike = float(match.group(2))
                 typ = match.group(3).upper()
                 S = self.nifty_spot if index == 'NIFTY' else self.banknifty_spot
                 T = 2.0/365.0
                 sigma = 0.15 # Fallback VIX
                 
                 g = self.greeks_calc.calculate_greeks(S, strike, T, sigma, typ)
                 tick.delta = g['delta']
                 tick.iv = sigma * 100
        except Exception:
             pass

    async def _aggregate_candle(self, tick: Tick):
        """Aggregate ticks into candles."""
        symbol = tick.symbol
        current_minute = tick.timestamp.replace(second=0, microsecond=0)
        
        if symbol not in self.candle_data:
            self.candle_data[symbol] = {
                'timestamp': current_minute,
                'open': tick.ltp, 'high': tick.ltp, 'low': tick.ltp, 'close': tick.ltp, 'volume': 0
            }
        else:
            c = self.candle_data[symbol]
            if c['timestamp'] < current_minute:
                # Emit Previous Candle
                await bus.publish(EventType.CANDLE, {'symbol': symbol, **c})
                # Start new
                self.candle_data[symbol] = {
                     'timestamp': current_minute,
                     'open': tick.ltp, 'high': tick.ltp, 'low': tick.ltp, 'close': tick.ltp, 'volume': 0
                }
            else:
                # Update
                c['high'] = max(c['high'], tick.ltp)
                c['low'] = min(c['low'], tick.ltp)
                c['close'] = tick.ltp

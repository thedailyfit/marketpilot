import asyncio
import logging
import random
import time
import csv
import os
import upstox_client # Added import
from dataclasses import asdict
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from core.config_manager import sys_config
from core.data_models import Tick, OrderBook, OrderBookLevel, Candle

class MarketDataAgent(BaseAgent):
    def __init__(self):
        super().__init__("MarketDataAgent")
        self.streamer_task = None
        self.active_symbol = getattr(sys_config, 'TRADING_SYMBOL', 'NSE_FO|NIFTY')
        self.current_candle: dict = {} 

    async def on_start(self):
        self._ensure_data_dir()
        
        # Subscribe to ticks for aggregation (useful for Backtest/Replay)
        bus.subscribe(EventType.MARKET_DATA, self.on_tick_event)

        if sys_config.MODE == "PAPER" and not sys_config.ACCESS_TOKEN:
            self.logger.info("Starting in PAPER MODE (Simulation) - No Access Token")
            self.streamer_task = asyncio.create_task(self._run_simulation())
        elif sys_config.MODE == "PAPER" and sys_config.ACCESS_TOKEN:
             self.logger.info("Starting in PAPER MODE (Live Data Feed)")
             self.streamer_task = asyncio.create_task(self._run_live_stream())
        else:
            self.logger.info("Starting in LIVE MODE (Upstox WebSocket)")
            # ... (rest of logic)
            if not sys_config.ACCESS_TOKEN:
                self.logger.warning("No Access Token found! Falling back to Simulation.")
                self.streamer_task = asyncio.create_task(self._run_simulation())
            else:
                self.streamer_task = asyncio.create_task(self._run_live_stream())

    async def on_stop(self):
        if self.streamer_task:
            self.streamer_task.cancel()
            try:
                await self.streamer_task
            except asyncio.CancelledError:
                pass

    async def on_tick_event(self, tick_data: dict):
        """Handle incoming ticks from EventBus (e.g. from ReplayAgent)."""
        # Convert dict back to Tick object if needed, or adjust _aggregate_candle to accept dict
        # tick = Tick(**tick_data) # unsafe if extra fields
        try:
            # We construct a minimal Tick for aggregation
            # Avoid processing our own emitted ticks if we were the source (to prevent double aggregation if logic changes)
            # But currently we don't emit and listen effectively in a loop, so this is safe for Replay.
            
            # _aggregate_candle expects a Tick object
            tick = Tick(
                symbol=tick_data['symbol'],
                ltp=tick_data['ltp'],
                timestamp=tick_data['timestamp'],
                volume=tick_data['volume'],
                depth=None
            )
            await self._aggregate_candle(tick)
        except Exception:
            pass

    async def initialize(self):
        self.logger.info("Initializing Market Data Agent...")
        self.active_symbol = getattr(sys_config, 'TRADING_SYMBOL', 'NSE_FO|NIFTY')
        self.logger.info(f"Initial Symbol: {self.active_symbol}")

    def update_config(self, symbol):
        self.active_symbol = symbol
        self.logger.info(f"MarketDataAgent switched to: {symbol}")

    def _ensure_data_dir(self):
        if not os.path.exists("data/history"):
            os.makedirs("data/history")

    def _log_tick_to_csv(self, tick: Tick):
        """Appends tick to daily CSV file."""
        try:
            # Sanitize symbol for filename (Windows disallows |)
            safe_symbol = tick.symbol.replace('|', '_').replace(':', '')
            filename = f"data/history/{safe_symbol}_ticks.csv"
            exists = os.path.exists(filename)
            
            with open(filename, 'a', newline='') as f:
                writer = csv.writer(f)
                if not exists:
                    writer.writerow(["Timestamp", "Symbol", "LTP", "Volume"])
                
                writer.writerow([tick.timestamp, tick.symbol, tick.ltp, tick.volume])
        except Exception:
            pass 

    def _generate_depth(self, price: float) -> OrderBook:
        spread = price * 0.0005
        best_bid = price - (spread / 2)
        best_ask = price + (spread / 2)
        bids = []
        asks = []
        for i in range(5):
            bid_p = best_bid - (i * 0.05)
            ask_p = best_ask + (i * 0.05)
            bids.append(OrderBookLevel(price=round(bid_p, 2), quantity=random.randint(50, 500), orders=random.randint(1, 5)))
            asks.append(OrderBookLevel(price=round(ask_p, 2), quantity=random.randint(50, 500), orders=random.randint(1, 5)))
        return OrderBook(timestamp=time.time(), bids=bids, asks=asks)

    async def _process_tick(self, tick: Tick):
        self._log_tick_to_csv(tick)
        tick_dict = asdict(tick)
        await bus.publish(EventType.MARKET_DATA, tick_dict)
        await self._aggregate_candle(tick)

    async def _aggregate_candle(self, tick: Tick):
        sym = tick.symbol
        ts = tick.timestamp
        price = tick.ltp
        candle_start = int(ts) 
        
        if sym not in self.current_candle or self.current_candle[sym].timestamp < candle_start:
            if sym in self.current_candle:
                completed_candle = self.current_candle[sym]
                completed_candle.complete = True
                await bus.publish(EventType.CANDLE_DATA, asdict(completed_candle))

            self.current_candle[sym] = Candle(
                symbol=sym,
                timestamp=candle_start,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=tick.volume
            )
        else:
            c = self.current_candle[sym]
            c.high = max(c.high, price)
            c.low = min(c.low, price)
            c.close = price
            c.volume += tick.volume

    async def start_demo_mode(self):
        """Switches to Demo Volatility Mode."""
        self.logger.info("Switching to DEMO SIMULATION MODE (Volatile Data)")
        if self.streamer_task:
            self.streamer_task.cancel()
        self.streamer_task = asyncio.create_task(self._run_demo_simulation())

    async def _run_demo_simulation(self):
        """Generates sine wave data to force Strategy Signals."""
        import math
        self.logger.info("!!! DEMO SIMULATION STARTED (Sine Wave) !!!")
        try:
            current_price = 19500.0
            step = 0
            while self.is_running:
                sym = self.active_symbol
                
                # Sine wave pattern: Amplitude 50, Period ~20 steps
                # RSI will swing high as price moves up, low as it moves down.
                change = math.sin(step * 0.3) * 10 + random.uniform(-2, 2)
                current_price += change
                current_price = round(current_price, 2)
                
                tick = Tick(
                    symbol=sym,
                    ltp=current_price,
                    timestamp=time.time(),
                    volume=random.randint(100, 500), # Higher volume
                    depth=None
                )
                
                await self._process_tick(tick)
                step += 1
                await asyncio.sleep(0.5) # Fast updates (2 ticks/sec)
                
        except Exception as e:
            self.logger.error(f"Demo Simulation Error: {e}")

    async def _run_simulation(self):
        print("!!! MARKET DATA SIMULATION STARTED (Enhanced) !!!")
        try:
            prices = {"NIFTY": 19500.0, "BANKNIFTY": 44500.0}
            last_symbol = ""
            current_price = 19500.0
            
            while self.is_running:
                sym = self.active_symbol
                base_sym = "BANKNIFTY" if "BANKNIFTY" in sym else "NIFTY"
            
                if base_sym != last_symbol:
                    current_price = prices.get(base_sym, 19500.0)
                    last_symbol = base_sym
                    self.logger.info(f"Price reset for {base_sym} to {current_price}")
                    
                change = random.uniform(-2, 3) 
                current_price += change
                current_price = round(current_price, 2)
                
                depth = self._generate_depth(current_price)
                tick = Tick(
                    symbol=sym,
                    ltp=current_price,
                    timestamp=time.time(),
                    volume=random.randint(1, 10),
                    depth=depth
                )
                
                await self._process_tick(tick)
                await asyncio.sleep(0.5) 
                
        except Exception as e:
            print(f"MARKET DATA ERROR: {e}")
            self.logger.error(f"Simulation Error: {e}")

    def get_history(self, symbol: str):
        """Returns aggregated 1-minute candle history."""
        # Clean Symbol
        safe_symbol = symbol.replace('|', '_').replace(':', '')
        filename = f"data/history/{safe_symbol}_ticks.csv"
        
        candles = []
        try:
            # 1. Try Reading CSV
            if os.path.exists(filename):
                df_data = []
                with open(filename, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        df_data.append(row)
                
                # Simple Aggregation (Slow but functional for demo)
                # In prod, use Pandas
                current_candle = None
                for row in df_data[-5000:]: # Limit to last 5000 ticks
                    price = float(row['LTP'])
                    ts = float(row['Timestamp'])
                    vol = int(row['Volume'])
                    candle_ts = int(ts) - (int(ts) % 60)
                    
                    if current_candle and current_candle['time'] == candle_ts:
                        current_candle['high'] = max(current_candle['high'], price)
                        current_candle['low'] = min(current_candle['low'], price)
                        current_candle['close'] = price
                        current_candle['volume'] += vol
                    else:
                        if current_candle: candles.append(current_candle)
                        current_candle = {'time': candle_ts, 'open': price, 'high': price, 'low': price, 'close': price, 'volume': vol}
                if current_candle: candles.append(current_candle)
        except Exception as e:
            self.logger.error(f"History Read Error: {e}")

        # 2. If Empty, Generate Synthetic History (User Experience Fallback)
        if len(candles) < 10:
            self.logger.info("Generating Synthetic History...")
            now = int(time.time())
            price = 19500.0 if "NIFTY" in symbol else 44500.0
            synthetic = []
            for i in range(1000): # 1000 candles
                t = now - ((1000 - i) * 60)
                change = random.uniform(-10, 12)
                o = price
                c = price + change
                h = max(o, c) + random.uniform(0, 5)
                l = min(o, c) - random.uniform(0, 5)
                synthetic.append({'time': t, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': random.randint(100, 5000)})
                price = c
            return synthetic
            
        return candles

    async def _run_live_stream(self):
        self.logger.info("Initializing Upstox WebSocket (Custom V3 Implementation)...")
        
        try:
            from core.upstox_stream import upstox_stream
            
            # Connect
            await upstox_stream.connect()
            
            # Keep alive loop
            while self.is_running:
                if not upstox_stream.is_connected:
                    self.logger.warning("WebSocket disconnected. Attempting reconnect...")
                    await upstox_stream.connect()
                await asyncio.sleep(5)
                
        except Exception as e:
            self.logger.error(f"Live Stream Failed: {e}")
            self.logger.info("Falling back to Simulation...")
            await self._run_simulation()

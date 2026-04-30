"""
Option Snapshot Service
Scheduled capture of option chain snapshots with Greeks and IV.
"""
import asyncio
import logging
from datetime import datetime, time, date
from typing import List, Dict, Optional
from pathlib import Path

try:
    import upstox_client
    from upstox_client import OptionApi, MarketQuoteApi
    HAS_UPSTOX = True
except ImportError:
    HAS_UPSTOX = False

from core.config_manager import sys_config
from core.event_bus import bus, EventType
from .chain_snapshot import chain_snapshot_engine, OptionSnapshot
from .vix_history import vix_history_store
from core.india_vix import vix_tracker


class SnapshotService:
    """
    Scheduled option chain snapshot service.
    
    Features:
    - Captures option chain every 3 minutes during market hours
    - Calculates IV and Greeks for each option
    - Stores to Parquet for historical replay
    - Records VIX for correlation analysis
    
    Market Hours: 09:15 - 15:30 IST
    Capture Window: 09:20 - 15:25 (avoid opening/closing noise)
    """
    
    # Market hours (IST)
    MARKET_OPEN = time(9, 15)
    MARKET_CLOSE = time(15, 30)
    CAPTURE_START = time(9, 20)
    CAPTURE_END = time(15, 25)
    
    # Symbols to capture
    DEFAULT_SYMBOLS = ["NIFTY", "BANKNIFTY"]
    
    def __init__(self):
        self.logger = logging.getLogger("SnapshotService")
        self.is_running = False
        self.capture_tasks: Dict[str, asyncio.Task] = {}
        
        # Config
        self.capture_interval = 180  # 3 minutes
        self.api_client = None
        
        # Stats
        self.captures_today = 0
        self.last_capture_time: Dict[str, int] = {}
        self.errors_today = 0
    
    async def start(self, symbols: List[str] = None, interval: int = 180):
        """
        Start scheduled snapshot capture.
        
        Args:
            symbols: List of underlyings to capture (default: NIFTY, BANKNIFTY)
            interval: Seconds between captures (default: 180 = 3 min)
        """
        if self.is_running:
            self.logger.warning("Snapshot service already running")
            return
        
        symbols = symbols or self.DEFAULT_SYMBOLS
        self.capture_interval = interval
        self.is_running = True
        
        self.logger.info(f"📸 Starting Snapshot Service for {symbols}")
        self.logger.info(f"   Interval: {interval}s | Capture: {self.CAPTURE_START} - {self.CAPTURE_END}")
        
        # Initialize API client
        await self._init_api_client()
        
        # Start capture loops for each symbol
        for symbol in symbols:
            task = asyncio.create_task(self._capture_loop(symbol))
            self.capture_tasks[symbol] = task
        
        # Start VIX tracking loop
        asyncio.create_task(self._vix_loop())
        
        self.logger.info("✅ Snapshot Service started")
    
    async def stop(self):
        """Stop all capture loops."""
        self.is_running = False
        
        for symbol, task in self.capture_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.capture_tasks.clear()
        vix_history_store.close()
        
        self.logger.info(f"📸 Snapshot Service stopped. Captures today: {self.captures_today}")
    
    async def _init_api_client(self):
        """Initialize Upstox API client."""
        if not HAS_UPSTOX:
            self.logger.warning("Upstox client not installed, using simulated data")
            return
        
        if not sys_config.ACCESS_TOKEN:
            self.logger.warning("No ACCESS_TOKEN, using simulated data")
            return
        
        try:
            config = upstox_client.Configuration()
            config.access_token = sys_config.ACCESS_TOKEN
            self.api_client = upstox_client.ApiClient(config)
            self.logger.info("Upstox API client initialized")
        except Exception as e:
            self.logger.error(f"Failed to init API client: {e}")
    
    async def _capture_loop(self, symbol: str):
        """Continuous capture loop for a symbol."""
        self.logger.info(f"Starting capture loop for {symbol}")
        
        while self.is_running:
            try:
                # Check if within capture window
                if not self._is_capture_time():
                    await asyncio.sleep(60)  # Check every minute
                    continue
                
                # Capture snapshot
                await self._capture_snapshot(symbol)
                
                # Wait for next interval
                await asyncio.sleep(self.capture_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Capture error for {symbol}: {e}")
                self.errors_today += 1
                await asyncio.sleep(30)  # Brief retry delay
    
    async def _capture_snapshot(self, symbol: str):
        """Capture a single snapshot for a symbol."""
        try:
            # Fetch option chain
            chain_data = await self._fetch_option_chain(symbol)
            
            if not chain_data:
                self.logger.warning(f"No chain data for {symbol}")
                return
            
            # Get spot price
            spot_price = await self._get_spot_price(symbol)
            
            if spot_price <= 0:
                self.logger.error(f"Invalid spot price for {symbol}")
                return
            
            # Capture snapshot with Greeks
            snapshots = await chain_snapshot_engine.capture_snapshot(
                symbol=symbol,
                spot_price=spot_price,
                chain_data=chain_data
            )
            
            self.captures_today += 1
            self.last_capture_time[symbol] = int(datetime.now().timestamp())
            
            self.logger.info(
                f"📸 {symbol}: Captured {len(snapshots)} options @ ₹{spot_price:.0f} "
                f"(Total: {self.captures_today})"
            )
            
        except Exception as e:
            self.logger.error(f"Snapshot capture failed for {symbol}: {e}")
            self.errors_today += 1
    
    async def _fetch_option_chain(self, symbol: str) -> List[dict]:
        """
        Fetch option chain from Upstox API.
        
        Args:
            symbol: NIFTY or BANKNIFTY
        
        Returns:
            List of option data dicts
        """
        if not self.api_client:
            return self._generate_simulated_chain(symbol)
        
        try:
            option_api = OptionApi(self.api_client)
            
            # Get instrument key
            instrument_key = f"NSE_INDEX|{symbol}"
            
            # Fetch option chain
            response = await asyncio.to_thread(
                option_api.get_option_chain,
                instrument_key=instrument_key
            )
            
            if not response or not response.data:
                return self._generate_simulated_chain(symbol)
            
            # Parse response into our format
            chain_data = []
            
            for option in response.data:
                try:
                    chain_data.append({
                        'strike': option.strike_price,
                        'expiry': option.expiry.strftime('%Y-%m-%d') if option.expiry else '',
                        'type': 'CE' if option.instrument_type == 'CE' else 'PE',
                        'ltp': option.last_price or 0,
                        'bid': option.bid_price or 0,
                        'ask': option.ask_price or 0,
                        'oi': option.open_interest or 0,
                        'volume': option.volume or 0,
                    })
                except Exception:
                    continue
            
            return chain_data
            
        except Exception as e:
            self.logger.error(f"API fetch error: {e}")
            return self._generate_simulated_chain(symbol)
    
    async def _get_spot_price(self, symbol: str) -> float:
        """Get current spot price for underlying."""
        if not self.api_client:
            # Simulated prices
            return 23100 if symbol == "NIFTY" else 49500
        
        try:
            quote_api = MarketQuoteApi(self.api_client)
            instrument_key = f"NSE_INDEX|{symbol}"
            
            response = await asyncio.to_thread(
                quote_api.get_market_quote_quotes,
                instrument_key=instrument_key
            )
            
            if response and response.data and instrument_key in response.data:
                return response.data[instrument_key].last_price or 0
            
            return 23100 if symbol == "NIFTY" else 49500
            
        except Exception as e:
            self.logger.error(f"Spot price fetch error: {e}")
            return 23100 if symbol == "NIFTY" else 49500
    
    def _generate_simulated_chain(self, symbol: str) -> List[dict]:
        """Generate simulated option chain for testing."""
        import random
        
        spot = 23100 if symbol == "NIFTY" else 49500
        step = 50 if symbol == "NIFTY" else 100
        
        # Get next weekly expiry
        today = date.today()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0:
            days_until_thursday = 7
        expiry = date(today.year, today.month, today.day + days_until_thursday)
        expiry_str = expiry.isoformat()
        
        chain = []
        
        # Generate ±10 strikes from ATM
        for i in range(-10, 11):
            strike = round(spot + (i * step), -1)
            
            for opt_type in ['CE', 'PE']:
                # Calculate realistic premium
                moneyness = (spot - strike) / spot
                
                if opt_type == 'CE':
                    if strike < spot:  # ITM
                        ltp = max(10, spot - strike + random.uniform(5, 20))
                    else:  # OTM
                        ltp = max(5, random.uniform(10, 100) * (1 - abs(moneyness)))
                else:  # PE
                    if strike > spot:  # ITM
                        ltp = max(10, strike - spot + random.uniform(5, 20))
                    else:  # OTM
                        ltp = max(5, random.uniform(10, 100) * (1 - abs(moneyness)))
                
                spread = ltp * 0.02  # 2% spread
                
                chain.append({
                    'strike': strike,
                    'expiry': expiry_str,
                    'type': opt_type,
                    'ltp': round(ltp, 2),
                    'bid': round(ltp - spread/2, 2),
                    'ask': round(ltp + spread/2, 2),
                    'oi': random.randint(10000, 500000),
                    'volume': random.randint(1000, 50000),
                })
        
        return chain
    
    async def _vix_loop(self):
        """Track and record VIX periodically."""
        while self.is_running:
            try:
                if self._is_market_hours():
                    vix_data = await vix_tracker.get_vix_data()
                    vix_history_store.record(vix_data.value, vix_data.regime)
                    self.logger.debug(f"VIX: {vix_data.value:.2f} ({vix_data.regime})")
                
                await asyncio.sleep(60)  # Record every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"VIX tracking error: {e}")
                await asyncio.sleep(60)
    
    def _is_capture_time(self) -> bool:
        """Check if within capture window."""
        now = datetime.now().time()
        return self.CAPTURE_START <= now <= self.CAPTURE_END
    
    def _is_market_hours(self) -> bool:
        """Check if within market hours."""
        now = datetime.now().time()
        return self.MARKET_OPEN <= now <= self.MARKET_CLOSE
    
    def get_status(self) -> dict:
        """Get service status."""
        return {
            "is_running": self.is_running,
            "captures_today": self.captures_today,
            "errors_today": self.errors_today,
            "capture_interval": self.capture_interval,
            "symbols": list(self.capture_tasks.keys()),
            "last_captures": self.last_capture_time,
            "is_capture_time": self._is_capture_time(),
            "is_market_hours": self._is_market_hours()
        }


# Singleton
snapshot_service = SnapshotService()

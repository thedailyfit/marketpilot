"""
FootprintAggregator - Volumetric Candle Engine
Converts tick-level trades into per-candle price buckets with buy/sell volume.
"""
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field
from core.event_bus import bus, EventType


@dataclass
class FootprintLevel:
    """Volume data at a specific price level within a candle."""
    price: float
    buy_vol: int = 0
    sell_vol: int = 0
    
    @property
    def total_vol(self) -> int:
        return self.buy_vol + self.sell_vol
    
    @property
    def delta(self) -> int:
        return self.buy_vol - self.sell_vol
    
    def to_dict(self) -> dict:
        return {"price": self.price, "buy": self.buy_vol, "sell": self.sell_vol, "delta": self.delta}


@dataclass
class FootprintCandle:
    """A single volumetric candle with price-level breakdown."""
    symbol: str
    start_time: int  # Unix timestamp (seconds)
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    levels: Dict[float, FootprintLevel] = field(default_factory=dict)
    poc_price: float = 0.0  # Point of Control
    
    def update(self, price: float, qty: int, side: str):
        """Update candle with a new tick."""
        # 1. Update OHLC
        if self.open == 0:
            self.open = price
        self.high = max(self.high, price)
        self.low = min(self.low, price) if self.low > 0 else price
        self.close = price
        self.volume += qty
        
        # 2. Update Volumetric Level
        if price not in self.levels:
            self.levels[price] = FootprintLevel(price=price)
        
        if side == 'BUY':
            self.levels[price].buy_vol += qty
        else:
            self.levels[price].sell_vol += qty
            
        # 3. Update POC (Point of Control)
        current_poc = self.levels.get(self.poc_price)
        new_level = self.levels[price]
        if not current_poc or new_level.total_vol > current_poc.total_vol:
            self.poc_price = price

    @property
    def delta(self) -> int:
        """Net delta for the entire candle."""
        return sum(lvl.delta for lvl in self.levels.values())
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "time": self.start_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "delta": self.delta,
            "poc": self.poc_price,
            "levels": {str(p): lvl.to_dict() for p, lvl in self.levels.items()}
        }


class FootprintAggregator:
    """
    Aggregates raw TICK events into FootprintCandles.
    Emits FOOTPRINT_UPDATE events for UI consumption.
    """
    def __init__(self, timeframe_sec: int = 60):
        self.logger = logging.getLogger("FootprintEngine")
        self.timeframe = timeframe_sec  # 60 = 1 Minute
        self.active_candles: Dict[str, FootprintCandle] = {}
        self.prev_ltp: Dict[str, float] = {}  # For tick direction heuristic
        self.is_running = False
        
    async def on_start(self):
        self.logger.info(f"Starting Footprint Engine (Timeframe: {self.timeframe}s)")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._process_tick)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Footprint Engine Stopped")
        
    async def _process_tick(self, tick_data: dict):
        """Process incoming TICK and aggregate into footprint candle."""
        if not self.is_running:
            return
            
        try:
            symbol = tick_data.get('symbol', '')
            ltp = float(tick_data.get('ltp', 0))
            if not symbol or ltp <= 0:
                return
            
            # Time bucketing
            now = int(datetime.now().timestamp())
            candle_start = now - (now % self.timeframe)
            
            # Check if we need a new candle
            if symbol not in self.active_candles or self.active_candles[symbol].start_time != candle_start:
                # Emit completed candle before creating new
                if symbol in self.active_candles:
                    await self._emit_final(self.active_candles[symbol])
                
                # Create new candle
                self.active_candles[symbol] = FootprintCandle(
                    symbol=symbol,
                    start_time=candle_start,
                    open=ltp, high=ltp, low=ltp, close=ltp
                )
            
            # Determine Side (Tick Direction Heuristic)
            prev = self.prev_ltp.get(symbol, ltp)
            side = 'BUY' if ltp >= prev else 'SELL'
            self.prev_ltp[symbol] = ltp
            
            # Quantity (Use 1 if not provided - common for index ticks)
            qty = int(tick_data.get('qty', 1) or 1)
            
            # Update Candle
            candle = self.active_candles[symbol]
            candle.update(ltp, qty, side)
            
            # Emit Update (throttle in production)
            await bus.publish(EventType.FOOTPRINT_UPDATE, candle.to_dict())
            
        except Exception as e:
            self.logger.error(f"Footprint Error: {e}")

    async def _emit_final(self, candle: FootprintCandle):
        """Finalize and store completed candle."""
        # Here we could store to DB for replay
        self.logger.debug(f"Candle Closed: {candle.symbol} @ {candle.start_time}")


# Singleton
footprint_engine = FootprintAggregator()

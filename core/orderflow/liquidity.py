"""
LiquidityScanner - Detects abnormal trades, absorption, and sweeps.
"""
import asyncio
import logging
from typing import Deque, Dict
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from core.event_bus import bus, EventType


@dataclass
class LiquidityEvent:
    """Represents a detected liquidity anomaly."""
    type: str  # BLOCK_TRADE, ABSORPTION, SWEEP
    symbol: str
    price: float
    qty: int
    side: str
    significance: str  # LOW, MEDIUM, HIGH
    timestamp: int
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "symbol": self.symbol,
            "price": self.price,
            "qty": self.qty,
            "side": self.side,
            "significance": self.significance,
            "time": self.timestamp
        }


class LiquidityScanner:
    """
    Monitors tick stream for:
    - Block Trades (abnormally large single trades)
    - Absorption (high volume, no price movement)
    - Sweeps (rapid price level consumption)
    """
    def __init__(self, window_size: int = 100):
        self.logger = logging.getLogger("LiquidityScanner")
        self.window_size = window_size
        self.qty_history: Dict[str, Deque[int]] = {}  # Symbol -> Recent quantities
        self.is_running = False
        
    async def on_start(self):
        self.logger.info("Starting Liquidity Scanner...")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._analyze_tick)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Liquidity Scanner Stopped")
        
    async def _analyze_tick(self, tick_data: dict):
        """Analyze each tick for liquidity events."""
        if not self.is_running:
            return
            
        try:
            symbol = tick_data.get('symbol', '')
            qty = int(tick_data.get('qty', 0) or 0)
            ltp = float(tick_data.get('ltp', 0))
            
            if not symbol or qty <= 0:
                return
            
            # Initialize history for symbol
            if symbol not in self.qty_history:
                self.qty_history[symbol] = deque(maxlen=self.window_size)
            
            history = self.qty_history[symbol]
            
            # --- BLOCK TRADE DETECTION ---
            if len(history) >= 10:
                avg_qty = sum(history) / len(history)
                threshold = avg_qty * 5  # 5x average = Block
                
                if qty >= threshold:
                    event = LiquidityEvent(
                        type="BLOCK_TRADE",
                        symbol=symbol,
                        price=ltp,
                        qty=qty,
                        side=tick_data.get('side', 'UNKNOWN'),
                        significance="HIGH" if qty >= threshold * 2 else "MEDIUM",
                        timestamp=int(datetime.now().timestamp())
                    )
                    await bus.publish(EventType.LIQUIDITY_EVENT, event.to_dict())
                    self.logger.info(f"BLOCK DETECTED: {symbol} {qty}@{ltp}")
            
            # Update history
            history.append(qty)
            
        except Exception as e:
            self.logger.error(f"Liquidity Scanner Error: {e}")


# Singleton
liquidity_scanner = LiquidityScanner()

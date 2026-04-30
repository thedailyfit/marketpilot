from dataclasses import dataclass, field
from typing import List, Optional
import time

@dataclass
class Tick:
    symbol: str
    ltp: float
    timestamp: float = field(default_factory=time.time)
    volume: int = 0
    depth: Optional['OrderBook'] = None

@dataclass
class OrderBookLevel:
    price: float
    quantity: int
    orders: int

@dataclass
class OrderBook:
    timestamp: float
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]

@dataclass
class Candle:
    symbol: str
    timestamp: float  # Start time of the candle
    open: float
    high: float
    low: float
    close: float
    volume: int
    complete: bool = False

@dataclass
class Signal:
    symbol: str
    signal_type: str  # BUY, SELL, EXIT
    strength: float   # 0.0 to 1.0
    timestamp: float
    reason: str
    strategy_id: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None

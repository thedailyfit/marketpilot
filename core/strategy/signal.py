"""
Signal Data Structure
Standardized packet for all strategy outputs.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime

@dataclass
class Signal:
    """
    Standardized trading signal.
    """
    symbol: str
    action: str  # BUY, SELL, EXIT, HOLD
    strategy_name: str
    timestamp: int
    
    # Execution details
    quantity: int = 1
    limit_price: float = 0.0  # 0.0 = Market
    stop_loss: float = 0.0
    take_profit: float = 0.0
    
    # Metadata
    confidence: float = 1.0     # 0.0 - 1.0
    setup_name: str = "UNKNOWN" # Specific pattern name
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "strategy": self.strategy_name,
            "timestamp": self.timestamp,
            "quantity": self.quantity,
            "price": self.limit_price,
            "sl": self.stop_loss,
            "tp": self.take_profit,
            "confidence": self.confidence,
            "setup": self.setup_name,
            "meta": self.metadata
        }

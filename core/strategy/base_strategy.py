"""
Base Strategy Interface
Abstract base class for all trading strategies.
"""
import logging
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from .signal import Signal

class BaseStrategy(ABC):
    """
    Abstract base class for strategies.
    Enforces standard interface for Signal Generation.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Strategy.{name}")
        self.is_active = True
        
    @abstractmethod
    async def calculate_signal(self, market_data: Dict[str, Any]) -> Optional[Signal]:
        """
        Analyze market data and return a Signal if setup found.
        
        Args:
            market_data: Dict containing 'ltp', 'ohlc', 'indicators', etc.
            
        Returns:
            Signal object or None
        """
        pass
        
    def validate_signal(self, signal: Signal) -> bool:
        """
        Basic sanity check on generated signal.
        """
        if not signal:
            return False
            
        if signal.action not in ["BUY", "SELL", "EXIT"]:
            self.logger.error(f"Invalid Action: {signal.action}")
            return False
            
        if signal.quantity <= 0:
            self.logger.error(f"Invalid Quantity: {signal.quantity}")
            return False
            
        return True

    def on_start(self):
        """Lifecycle hook: Strategy started."""
        self.logger.info(f"🟢 Strategy {self.name} Started")
        
    def on_stop(self):
        """Lifecycle hook: Strategy stopped."""
        self.logger.info(f"🔴 Strategy {self.name} Stopped")

    def update_parameters(self, params: Dict):
        """Update strategy parameters dynamically."""
        pass

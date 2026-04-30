from abc import ABC, abstractmethod
from typing import Optional, Dict
from core.data_models import Tick, Candle, Signal

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name
        self.params: Dict = {}

    @abstractmethod
    def on_tick(self, tick: Tick) -> Optional[Signal]:
        """Process high-frequency tick data."""
        pass

    @abstractmethod
    def on_candle(self, candle: Candle) -> Optional[Signal]:
        """Process aggregated candle data."""
        pass

    @abstractmethod
    def on_features(self, features: dict) -> Optional[Signal]:
        """Process pre-calculated features (Greeks, Indicators)."""
        pass

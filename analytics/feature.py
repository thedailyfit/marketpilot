import logging
import asyncio
from typing import List, Dict
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from core.data_models import Candle

class FeatureAgent(BaseAgent):
    def __init__(self):
        super().__init__("FeatureAgent")
        self.candles: Dict[str, List[float]] = {} # Symbol -> Close Prices
        
    async def on_start(self):
        self.logger.info("Feature Analytics Engine Started")
        # Subscribe to Candle Data
        bus.subscribe(EventType.CANDLE_DATA, self.on_candle)

    async def on_stop(self):
        pass

    async def on_candle(self, data: dict):
        """Process incoming candle and compute features."""
        try:
            # We assume data is a dict representation of Candle
            sym = data['symbol']
            close = data['close']
            
            if sym not in self.candles:
                self.candles[sym] = []
            
            # Maintain rolling window of 50 periods
            self.candles[sym].append(close)
            if len(self.candles[sym]) > 50:
                self.candles[sym].pop(0)

            # Calculate Indicators
            features = {
                "symbol": sym,
                "timestamp": data['timestamp'],
                "rsi_14": self._calc_rsi(self.candles[sym], 14),
                "ema_9": self._calc_ema(self.candles[sym], 9),
                "ema_21": self._calc_ema(self.candles[sym], 21),
                "delta": self._calc_approx_delta(close), # Placeholder
                "theta": -0.5 # Placeholder (Theta Decay)
            }
            
            # self.logger.info(f"Features: {features}")
            await bus.publish(EventType.MARKET_FEATURES, features)
            
        except Exception as e:
            self.logger.error(f"Feature Calc Error: {e}")

    def _calc_rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        
        # Simple RSI implementation
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0.0001 # Avoid div/0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calc_ema(self, prices: List[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1]
        
        # Simple EMA calculation
        # Multiplier: (2 / (Time periods + 1) )
        k = 2 / (period + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = (p * k) + (ema * (1 - k))
        return round(ema, 2)

    def _calc_approx_delta(self, price: float) -> float:
        """Approximation of Delta for ATM Option."""
        return 0.50 # ATM Call Delta is roughly 0.5

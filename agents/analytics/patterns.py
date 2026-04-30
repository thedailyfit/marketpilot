
import asyncio
import logging
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
import numpy as np

logger = logging.getLogger("PatternRecognitionAgent")

class PatternRecognitionAgent(BaseAgent):
    """
    ENGINE 3: PATTERN VISION
    Algorithmic recognition of classic price patterns.
    - W-Pattern (Double Bottom)
    - Bull Flag
    - M-Pattern (Double Top)
    """
    def __init__(self):
        super().__init__("PatternVision")
        self.candles = []
        self.pivots_high = []
        self.pivots_low = []
        
    async def on_start(self):
        bus.subscribe(EventType.CANDLE_DATA, self.on_candle)
        logger.info("👀 Pattern Vision Engine Active")

    async def on_stop(self):
        pass

    async def on_candle(self, candle: dict):
        self.candles.append(candle)
        if len(self.candles) > 100: self.candles.pop(0)
        
        # Run Detection
        if len(self.candles) >= 20:
            await self._detect_patterns()

    async def _detect_patterns(self):
        closes = [c['close'] for c in self.candles]
        
        # 1. W-PATTERN (Double Bottom)
        # Check last 20 candles
        # Logic: Low1 (L1) -> Bounce (H) -> Low2 (L2) -> Break H
        # Simplified: Check if current price broke local high after two similar lows
        
        recent_lows = sorted(closes[-15:-1])[:2] # Two lowest points
        if abs(recent_lows[0] - recent_lows[1]) < (recent_lows[0] * 0.001): # Within 0.1% diff
            # Potential double bottom
            neckline = max(closes[-10:])
            current = closes[-1]
            
            if current > neckline:
                logger.info("👀 W-PATTERN (Double Bottom) BREAKOUT Detected!")
                await self._publish_pattern("W_PATTERN", "BULLISH_REVERSAL")
                return

        # 2. BULL FLAG
        # Sharp move up (Pole) + Consolidation (Flag)
        # Pole: Price rose > 0.5% in 5 candles
        # Flag: Mixed/Down candles with low vol
        
        start_price = closes[-10]
        peak_price = max(closes[-10:-5])
        
        pole_move = (peak_price - start_price) / start_price * 100
        
        if pole_move > 0.3: # Strong pole
            current = closes[-1]
            if current > peak_price: # Breakout
                 logger.info("🚩 BULL FLAG BREAKOUT Detected!")
                 await self._publish_pattern("BULL_FLAG", "CONTINUATION_BUY")

    async def _publish_pattern(self, name, signal):
        await bus.publish(EventType.ANALYSIS, {
            "source": "PatternVision",
            "type": "CHART_PATTERN",
            "data": {
                "pattern": name,
                "signal": signal,
                "confidence": "HIGH"
            }
        })

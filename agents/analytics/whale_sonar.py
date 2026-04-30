
import asyncio
import logging
import collections
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("WhaleAgent")

class WhaleAgent(BaseAgent):
    """
    ENGINE 15: THE WHALE SONAR (Order Flow)
    Detects Hidden Accumulation/Distribution (Icebergs).
    Logic: Price is Flat + Volume is Huge = Big Player Loading.
    """
    def __init__(self):
        super().__init__("WhaleAgent")
        self.tick_buffer = collections.deque(maxlen=100) # Last 100 ticks
        self.sonar_status = "QUIET" 

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("🐳 The Whale Sonar (Order Flow) Active")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        price = tick['ltp']
        # Simulated volume since tick data might not have it in paper mode
        # In prod: vol = tick['volume']
        vol = tick.get('last_traded_quantity', 1) 
        
        self.tick_buffer.append((price, vol))
        
        if len(self.tick_buffer) < 50:
            return

        # 1. Analyze Price Range
        prices = [x[0] for x in self.tick_buffer]
        high = max(prices)
        low = min(prices)
        price_range_pct = (high - low) / low * 100
        
        # 2. Analyze Volume Density
        total_vol = sum(x[1] for x in self.tick_buffer)
        avg_vol = total_vol / len(self.tick_buffer)
        
        # LOGIC:
        # If Price Range is Tiny (< 0.05%) AND Volume is Massive (> Threshold)
        # Then -> Accumulation
        
        is_flat = price_range_pct < 0.05
        # Simulate volume spike for logic check as real tick vol is sparse here
        is_huge_vol = avg_vol > 500 # Threshold would be dynamic in prod
        
        if is_flat and is_huge_vol:
            self.sonar_status = "ACCUMULATION_DETECTED"
            logger.info("🐳 WHALE ALERT: Iceberg Detected! (Flat Price + Huge Vol). Expect Breakout.")
            
            await bus.publish(EventType.ANALYSIS, {
                "source": "WhaleAgent",
                "type": "ORDER_FLOW",
                "data": {
                    "signal": "ACCUMULATION_BUY",
                    "confidence": 0.85,
                    "reason": "ICEBERG_ORDER"
                }
            })
            self.tick_buffer.clear() # Reset
            
        else:
            self.sonar_status = "QUIET"

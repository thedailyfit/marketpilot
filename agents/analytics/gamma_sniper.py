
import logging
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("GammaSniperAgent")

class GammaSniperAgent(BaseAgent):
    """
    ENGINE 35: THE GAMMA SNIPER (Max Pain)
    Targets original liquidity clusters and Max Pain gravity points.
    """
    def __init__(self):
        super().__init__("GammaSniperAgent")
        self.max_pain_level = 0.0
        self.gamma_flip_zone = 0.0
        self.gravity_strength = "LOW"

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("🎯 Gamma Sniper (Max Pain) Initialized")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        price = tick['ltp']
        # SIMULATED MAX PAIN LOGIC
        # In prod: Analyze full Option Chain OI to find min-loss strike
        if self.max_pain_level == 0:
            self.max_pain_level = round(price / 100) * 100
            
        diff = abs(price - self.max_pain_level)
        if diff > 150:
            self.gravity_strength = "HIGH"
            logger.info(f"🎯 GRAVITY PULL: Price is {diff:.1f} pts away from Max Pain ({self.max_pain_level})")
            await bus.publish(EventType.ANALYSIS, {
                "source": "GammaSniperAgent",
                "type": "GRAVITY_PULL",
                "data": {"target": self.max_pain_level, "strength": "HIGH", "direction": "UP" if price < self.max_pain_level else "DOWN"}
            })
        else:
            self.gravity_strength = "LOW"

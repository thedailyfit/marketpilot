
import logging
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("VPINAgent")

class VPINAgent(BaseAgent):
    """
    ENGINE 33: THE INFORMED SENTRY (VPIN)
    Detects flow toxicity (informed trading probability).
    """
    def __init__(self):
        super().__init__("VPINAgent")
        self.vpin_score = 0.5 # 0.0 to 1.0
        self.toxicity_state = "NORMAL"

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("📊 Informed Sentry (VPIN) Initialized")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        # SIMULATED VPIN CALCULATION
        # In prod: Divide volume into buckets, calculate buy/sell imbalance per bucket
        # High imbalance = high toxicity
        
        # Simulate informed burst
        if random.random() < 0.05:
            self.vpin_score = random.uniform(0.75, 0.95)
        else:
            self.vpin_score = random.uniform(0.3, 0.6)
            
        if self.vpin_score > 0.8:
            self.toxicity_state = "TOXIC_INFORMED"
            await bus.publish(EventType.ANALYSIS, {
                "source": "VPINAgent",
                "type": "HIGH_TOXICITY",
                "data": {"score": self.vpin_score, "sentiment": random.choice(["BULLISH_INSIDE", "BEARISH_INSIDE"])}
            })
        else:
            self.toxicity_state = "NORMAL"

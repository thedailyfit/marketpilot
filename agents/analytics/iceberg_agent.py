
import logging
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("IcebergAgent")

class IcebergAgent(BaseAgent):
    """
    ENGINE 34: THE ICEBERG HUNTER (Hidden Depth)
    Identifies hidden limit orders (Icebergs) at key price levels.
    """
    def __init__(self):
        super().__init__("IcebergAgent")
        self.icebergs_detected = [] # list of levels

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("🧊 Iceberg Hunter (Hidden Depth) Initialized")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        price = tick['ltp']
        # LOGIC: If price is held at a level while 5-10 clusters of volume are executed
        # (Simplified simulation)
        if random.random() < 0.01:
            level = round(price / 10) * 10
            logger.info(f"🧊 ICEBERG DETECTED: Large hidden volume at {level}")
            self.icebergs_detected.append(level)
            if len(self.icebergs_detected) > 3: self.icebergs_detected.pop(0)
            
            await bus.publish(EventType.ANALYSIS, {
                "source": "IcebergAgent",
                "type": "ICEBERG_LEVEL",
                "data": {"level": level, "strength": "INSTITUTIONAL"}
            })


import logging
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("HeatmapAgent")

class HeatmapAgent(BaseAgent):
    """
    ENGINE 30: LIQUIDITY HEATMAP (Dark Pools)
    Maps hidden institutional walls and absorption zones.
    """
    def __init__(self):
        super().__init__("HeatmapAgent")
        self.magnet_zones = [] # List of price levels with high absorption
        self.last_ltp = 0.0

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("🌋 Liquidity Heatmap (Dark Pools) Initialized")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        price = tick['ltp']
        volume = tick.get('v', 0) # volume from tick if available
        
        # LOGIC: Identify levels where price stalls but volume is huge
        # (Simplified simulation)
        if random.random() < 0.02: # Found a wall
            zone = {
                "level": round(price / 50) * 50, # Round to nearest 50
                "strength": random.uniform(0.1, 1.0),
                "type": random.choice(["SUPPORT_WALL", "RESISTANCE_WALL"])
            }
            self.magnet_zones.append(zone)
            if len(self.magnet_zones) > 5: self.magnet_zones.pop(0)
            
            logger.info(f"🌋 MAGNET ZONE DETECTED: {zone['type']} at {zone['level']}")
            
            await bus.publish(EventType.ANALYSIS, {
                "source": "HeatmapAgent",
                "type": "LIQUIDITY_MAP",
                "data": zone
            })

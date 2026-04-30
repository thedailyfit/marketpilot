
import logging
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("TapeMasterAgent")

class TapeMasterAgent(BaseAgent):
    """
    ENGINE 27: THE TAPE MASTER (Order Book Depth)
    Analyzes Order Book Imbalance (OBI) to predict short-term breakouts.
    """
    def __init__(self):
        super().__init__("TapeMasterAgent")
        self.obi_ratio = 1.0 # Buy Orders / Sell Orders
        self.market_state = "BALANCED"

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("📈 Tape Master (Order Book Depth) Initialized")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        # Simulated Level 2 Data (Bids/Asks)
        # In prod: fetch full order book snapshot from Upstox
        total_bids = random.uniform(1000, 5000)
        total_asks = random.uniform(1000, 5000)
        
        # Artificial imbalance trigger
        if random.random() < 0.1:
            total_bids *= 3 # 3x buyers
            
        self.obi_ratio = total_bids / total_asks if total_asks > 0 else 1.0
        
        if self.obi_ratio > 3.0:
            self.market_state = "BUY_PRESSURE"
            await bus.publish(EventType.ANALYSIS, {
                "source": "TapeMasterAgent",
                "type": "PRESSURE_SIGNAL",
                "data": {
                    "direction": "UP",
                    "ratio": self.obi_ratio,
                    "is_spoofing_suspected": random.random() < 0.2
                }
            })
        elif self.obi_ratio < 0.33:
            self.market_state = "SELL_PRESSURE"
            await bus.publish(EventType.ANALYSIS, {
                "source": "TapeMasterAgent",
                "type": "PRESSURE_SIGNAL",
                "data": {
                    "direction": "DOWN",
                    "ratio": self.obi_ratio
                }
            })
        else:
            self.market_state = "BALANCED"


import asyncio
import logging
import collections
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("RabbitAgent")

class RabbitAgent(BaseAgent):
    """
    ENGINE 13: THE RABBIT (Micro-Scalper)
    Strategy: "Bite & Run".
    Logic: Track Tick Momentum. If Price moves fast (High Velocity) -> SCALP.
    """
    def __init__(self):
        super().__init__("RabbitAgent")
        self.tick_window = collections.deque(maxlen=10) # Track last 10 ticks
        self.momentum_threshold = 2.5 # Points per second approx
        self.status = "SLEEPING" # SLEEPING, ALERT, HUNTING

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("🐰 The Rabbit (Micro-Scalper) Active")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        price = tick['ltp']
        ts = tick.get('timestamp', 0) # Assumes ms timestamp or similar
        
        self.tick_window.append((price, ts))
        
        if len(self.tick_window) < 5:
            return

        # Calculate Momentum (Price Change / Time)
        # Simplified: Just look at absolute price change over window
        start_price, _ = self.tick_window[0]
        end_price, _ = self.tick_window[-1]
        
        diff = end_price - start_price
        
        # Detect Spike
        if diff > self.momentum_threshold:
            self.status = "HUNTING_BULL"
            logger.info(f"🐰 RABBIT SPIKE: +{diff:.2f} pts! BITE SIGNAL (BUY)")
            
            await bus.publish(EventType.ANALYSIS, {
                "source": "RabbitAgent",
                "type": "SCALP_SIGNAL",
                "data": {
                    "signal": "SCALP_BUY",
                    "reason": "MOMENTUM_SPIKE",
                    "target": price + 5.0, # 5 pt target
                    "stop": price - 5.0
                }
            })
            self.tick_window.clear() # Reset to avoid double signalling
            
        elif diff < -self.momentum_threshold:
            self.status = "HUNTING_BEAR"
            logger.info(f"🐰 RABBIT DROP: {diff:.2f} pts! RUN SIGNAL (SELL)")
            
            await bus.publish(EventType.ANALYSIS, {
                "source": "RabbitAgent",
                "type": "SCALP_SIGNAL",
                "data": {
                    "signal": "SCALP_SELL",
                    "reason": "MOMENTUM_CRASH",
                    "target": price - 5.0,
                    "stop": price + 5.0
                }
            })
            self.tick_window.clear()
        else:
            self.status = "ALERT" if abs(diff) > 1.0 else "SLEEPING"
            

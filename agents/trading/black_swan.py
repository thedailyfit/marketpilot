
import logging
import collections
import time
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("BlackSwanAgent")

class BlackSwanAgent(BaseAgent):
    """
    ENGINE 23: THE BLACK SWAN (Crash Protection)
    Survival Intelligence. Detects flash crashes.
    """
    def __init__(self):
        super().__init__("BlackSwanAgent")
        self.tick_history = collections.deque(maxlen=200) # Fast 200 ticks
        self.kill_switch_active = False

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("🦢 Black Swan Flash Crash Protection Active")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        if self.kill_switch_active:
            return

        price = tick['ltp']
        self.tick_history.append((price, time.time()))
        
        if len(self.tick_history) < 50:
            return

        # Analyze Acceleration (Last 50 ticks vs Start of window)
        start_price, start_ts = self.tick_history[0]
        curr_price, curr_ts = self.tick_history[-1]
        
        elapsed = curr_ts - start_ts
        if elapsed == 0: return
        
        drop_pct = (start_price - curr_price) / start_price * 100
        velocity = drop_pct / elapsed # % drop per second
        
        # LOGIC: If price drops > 1% in < 2 seconds -> EMERGENCY
        if drop_pct > 1.0 and elapsed < 2.0:
            logger.critical(f"🛑 BLACK SWAN DETECTED! Drop: {drop_pct:.2f}% in {elapsed:.2f}s! Velocity: {velocity:.2f}%/s")
            self.kill_switch_active = True
            
            # TRIGGER KILL SWITCH
            await bus.publish(EventType.RISK, {
                "source": "BlackSwanAgent",
                "type": "KILL_SWITCH",
                "data": {
                    "reason": "Flash Crash Detected",
                    "drop_pct": drop_pct,
                    "velocity": velocity
                }
            })

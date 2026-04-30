
import asyncio
import logging
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("TapeReaderAgent")

class TapeReaderAgent(BaseAgent):
    """
    ENGINE 5: VELOCITY VISION
    Monitors the 'Heartbeat' of the market (Ticks Per Second).
    High Speed = High Interest (Gamma/Panic).
    """
    def __init__(self):
        super().__init__("TapeReaderAgent")
        self.tick_counter = 0
        self.tps_history = []
        self.current_tps = 0
        self.panic_threshold = 50 # TPS threshold (Lower for prototype)
        
    async def on_start(self):
        bus.subscribe(EventType.MARKET_DATA, self.on_tick)
        bus.subscribe(EventType.TICK, self.on_tick) # Listen to both feed types
        logger.info("⚡ Velocity Vision (Tape Reader) Active")
        asyncio.create_task(self._velocity_loop())

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        self.tick_counter += 1

    async def _velocity_loop(self):
        """Calculates TPS every second."""
        while self.is_running:
            self.current_tps = self.tick_counter
            self.tick_counter = 0 # Reset
            
            self.tps_history.append(self.current_tps)
            if len(self.tps_history) > 60: self.tps_history.pop(0)
            
            # Analysis
            if self.current_tps > self.panic_threshold:
                logger.info(f"⚡ VELOCITY SPIKE: {self.current_tps} TPS! (Gamma Scalp Setup)")
                
                await bus.publish(EventType.SYSTEM_STATUS, {
                    "type": "VELOCITY_ALERT",
                    "tps": self.current_tps,
                    "level": "EXTREME",
                    "message": "Market Speed Exploding! Scalp Opportunity."
                })
            
            await asyncio.sleep(1)

    def get_market_temperature(self):
        if self.current_tps > self.panic_threshold: return "BOILING"
        if self.current_tps > (self.panic_threshold / 2): return "HOT"
        return "COLD"


import asyncio
import logging
from datetime import datetime, timedelta
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("TrapHunterAgent")

class TrapHunterAgent(BaseAgent):
    """
    ENGINE 7: THE LIQUIDITY TRAP (Stop-Hunt Sniper)
    Detects when price breaks a level but reclaims it quickly (Liquidity Grab).
    """
    def __init__(self):
        super().__init__("TrapHunterAgent")
        self.levels = {"support": 24000.0, "resistance": 24500.0} # Dynamic in prod
        self.breakdown_time = None
        self.is_below_support = False
        
    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("🎣 Liquidity Trap Hunter (Stop-Hunt Sniper) Active")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        price = tick['ltp']
        
        # 1. Check for Breakdown
        if not self.is_below_support and price < self.levels['support']:
            self.is_below_support = True
            self.breakdown_time = datetime.now()
            logger.info(f"🎣 POTENTIAL TRAP: Price broke support {self.levels['support']}!")
            
        # 2. Check for Reclaim (The Trap)
        elif self.is_below_support and price > self.levels['support']:
            if self.breakdown_time:
                time_diff = (datetime.now() - self.breakdown_time).total_seconds()
                
                # If reclaimed within 3 mins (180s) -> IT WAS A TRAP!
                if time_diff < 180:
                    logger.info(f"🎣 TRAP CONFIRMED! Support reclaimed in {int(time_diff)}s. STOP HUNT COMPLETE.")
                    
                    await bus.publish(EventType.ANALYSIS, {
                        "source": "TrapHunterAgent",
                        "type": "TRAP_SIGNAL",
                        "data": {
                            "signal": "STRONG_BUY_REVERSAL",
                            "reason": "LIQUIDITY_GRAB_COMPLETE",
                            "stop_loss": self.levels['support'] - 10
                        }
                    })
            
            # Reset
            self.is_below_support = False
            self.breakdown_time = None

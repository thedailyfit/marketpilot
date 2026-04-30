
import asyncio
import logging
from datetime import datetime, time
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("GapAgent")

class GapAgent(BaseAgent):
    """
    ENGINE 11: THE GAP TACTICIAN (Opening Range Expert)
    Monitors First 15 Minutes (9:15-9:30).
    Enforces 'No Fly Zone' until range is broken.
    """
    def __init__(self):
        super().__init__("GapAgent")
        self.orb_high = None
        self.orb_low = None
        self.orb_complete = False
        self.market_start = time(9, 15)
        self.orb_end = time(9, 30)
        self.status = "PRE_MARKET" # PRE_MARKET, FORMING, ACTIVE, BREAKOUT

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("🚦 Gap Tactician (Opening Range) Active")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        now = datetime.now().time()
        price = tick['ltp']
        
        # 1. Forming Phase (9:15 - 9:30)
        if now >= self.market_start and now < self.orb_end:
            self.status = "FORMING_ORB"
            if self.orb_high is None: 
                self.orb_high = price
                self.orb_low = price
            else:
                self.orb_high = max(self.orb_high, price)
                self.orb_low = min(self.orb_low, price)
                
        # 2. Active Phase (After 9:30)
        elif now >= self.orb_end:
            if self.orb_high is None: # Late start catch
                self.orb_high = price
                self.orb_low = price
                
            if not self.orb_complete:
                self.orb_complete = True
                self.status = "INSIDE_ZONE"
                logger.info(f"🚦 ORB COMPLETE: High {self.orb_high} | Low {self.orb_low} (Range: {self.orb_high - self.orb_low})")
            
            # Check Breakout
            if self.status == "INSIDE_ZONE":
                if price > self.orb_high:
                    self.status = "BULLISH_BREAKOUT"
                    logger.info("🚦 ORB BREAKOUT (BULLISH) DETECTED!")
                    await self._publish_signal("BUY")
                    
                elif price < self.orb_low:
                    self.status = "BEARISH_BREAKDOWN"
                    logger.info("🚦 ORB BREAKDOWN (BEARISH) DETECTED!")
                    await self._publish_signal("SELL")

    async def _publish_signal(self, direction):
        await bus.publish(EventType.ANALYSIS, {
            "source": "GapAgent",
            "type": "ORB_SIGNAL",
            "data": {
                "signal": f"ORB_{direction}",
                "high": self.orb_high,
                "low": self.orb_low
            }
        })

    def check_zone(self, price):
        """Returns True if price is inside the No Fly Zone."""
        if self.status == "FORMING_ORB":
            return True, "Forming Opening Range (Wait till 9:30)"
            
        if self.status == "INSIDE_ZONE":
            if self.orb_low <= price <= self.orb_high:
                return True, "Inside No Fly Zone (Wait for Breakout)"
                
        return False, "OK"

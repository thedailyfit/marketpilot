
import logging
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("FIITrackerAgent")

class FIITrackerAgent(BaseAgent):
    """
    ENGINE 18: THE FII TRACKER (OI Power)
    Analyzes Open Interest (OI) to validate trend strength.
    """
    def __init__(self):
        super().__init__("FIITrackerAgent")
        self.last_oi = 0
        self.last_price = 0
        self.oi_insight = "NEUTRAL"

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("🏦 FII Tracker (OI Power) Initialized")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        price = tick['ltp']
        # Simulated OI data (Upstox gives this in specific OI packets, but we simulate for logic)
        current_oi = tick.get('oi', 10000000) 
        
        if self.last_price == 0:
            self.last_price = price
            self.last_oi = current_oi
            return

        price_diff = price - self.last_price
        oi_diff = current_oi - self.last_oi
        
        # LOGIC:
        # Price UP + OI UP = LONG BUILDUP (Bullish, Real)
        # Price UP + OI DOWN = SHORT COVERING (Fake move, Retail)
        # Price DOWN + OI UP = SHORT BUILDUP (Bearish, Real)
        # Price DOWN + OI DOWN = LONG UNWINDING (Exiting)

        if price_diff > 0 and oi_diff > 1000:
            self.oi_insight = "LONG_BUILDUP"
        elif price_diff > 0 and oi_diff < -1000:
            self.oi_insight = "SHORT_COVERING"
        elif price_diff < 0 and oi_diff > 1000:
            self.oi_insight = "SHORT_BUILDUP"
        elif price_diff < 0 and oi_diff < -1000:
            self.oi_insight = "LONG_UNWINDING"
        else:
            self.oi_insight = "STAGNANT"

        # Update last state
        self.last_price = price
        self.last_oi = current_oi

    def check_trend_validity(self, direction):
        """Returns True if the OI supports the price direction."""
        if direction == "BUY":
            if self.oi_insight == "LONG_BUILDUP":
                return True, "Strong Smart Money Buying"
            if self.oi_insight == "SHORT_COVERING":
                return False, "Fake Trend (Short Covering only)"
        
        if direction == "SELL":
            if self.oi_insight == "SHORT_BUILDUP":
                return True, "Strong Smart Money Selling"
            if self.oi_insight == "LONG_UNWINDING":
                return False, "Weak Trend (Long Unwinding)"
                
        return True, "OK (Neutral OI)"

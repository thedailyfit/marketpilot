
import asyncio
import logging
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("MacroAgent")

class MacroAgent(BaseAgent):
    """
    ENGINE 8: THE GLOBAL TETHER (Macro Correlation)
    Monitors Inter-market assets (USDINR, Crude) to validate Equity trends.
    """
    def __init__(self):
        super().__init__("MacroAgent")
        self.usdinr_change = 0.0
        self.macro_status = "NEUTRAL" # BULLISH, BEARISH

    async def on_start(self):
        logger.info("🌍 Global Tether (Macro Correlation) Active")
        asyncio.create_task(self._macro_loop())

    async def on_stop(self):
        pass

    async def _macro_loop(self):
        """Simulates Global Macro Moves."""
        while self.is_running:
            # Random Simulation
            change = random.uniform(-0.3, 0.3) # Daily % Change
            self.usdinr_change = change
            
            # Logic: USDINR Negative -> Good for Stocks (Bullish)
            # Logic: USDINR Positive -> Bad for Stocks (Bearish)
            
            if self.usdinr_change > 0.15:
                self.macro_status = "BEARISH_MACRO"
            elif self.usdinr_change < -0.15:
                self.macro_status = "BULLISH_MACRO"
            else:
                self.macro_status = "NEUTRAL"
                
            # Publish if significant
            if self.macro_status != "NEUTRAL":
                logger.info(f"🌍 MACRO UPDATE: USDINR {self.usdinr_change:+.2f}% -> {self.macro_status}")
                
            await asyncio.sleep(10) # Heavy update every 10s

    def check_veto(self, direction):
        """
        Returns True if the trade direction CONFLICTS with Macro.
        """
        if direction == "BUY" and self.macro_status == "BEARISH_MACRO":
            return True, "USDINR Spiking (+Rupee Weakness)"
            
        if direction == "SELL" and self.macro_status == "BULLISH_MACRO":
            return True, "USDINR Crashing (+Rupee Strength)"
            
        return False, "OK"

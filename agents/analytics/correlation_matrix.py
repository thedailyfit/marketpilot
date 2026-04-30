
import logging
import random
from core.base_agent import BaseAgent

logger = logging.getLogger("CorrelationAgent")

class CorrelationAgent(BaseAgent):
    """
    ENGINE 22: THE CORRELATION MATRIX (Global Sync)
    Ensures local trades align with the global market tide.
    """
    def __init__(self):
        super().__init__("CorrelationAgent")
        self.global_status = "STABLE" # STABLE, WEAK, CRASHING
        self.nasdaq_change = 0.0
        self.gift_nifty_change = 0.0

    async def on_start(self):
        logger.info("🌐 Global Correlation Matrix Active")

    async def on_stop(self):
        pass

    def update_global_data(self):
        """Simulates fetching global index data."""
        self.nasdaq_change = random.uniform(-3.0, 1.0)
        self.gift_nifty_change = random.uniform(-2.0, 1.0)
        
        if self.nasdaq_change < -2.0 or self.gift_nifty_change < -1.5:
            self.global_status = "CRASHING"
        elif self.nasdaq_change < -1.0:
            self.global_status = "WEAK"
        else:
            self.global_status = "STABLE"

    def check_correlation_veto(self, direction):
        """Blocks Long trades if global markets are crashing."""
        self.update_global_data()
        if direction == "BUY" and self.global_status == "CRASHING":
            return True, f"Global Contagion: Nasdaq {self.nasdaq_change:.1f}%, Gift Nifty {self.gift_nifty_change:.1f}%"
        return False, "Global Correlation OK"

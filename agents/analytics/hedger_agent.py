
import logging
import random
from core.base_agent import BaseAgent

logger = logging.getLogger("HedgerAgent")

class HedgerAgent(BaseAgent):
    """
    ENGINE 31: CROSS-ASSET HEDGER (Macro-Correlation)
    Monitors Currency/Bonds to predict sector pivots.
    """
    def __init__(self):
        super().__init__("HedgerAgent")
        self.usdinr = 83.50
        self.bond_yield = 7.10
        self.active_sector_bias = "BALANCED"

    async def on_start(self):
        logger.info("💸 Cross-Asset Hedger (Macro) Active")

    async def on_stop(self):
        pass

    def update_macro(self):
        """Simulates fetching macro data."""
        self.usdinr += random.uniform(-0.1, 0.1)
        self.bond_yield += random.uniform(-0.02, 0.02)
        
        # LOGIC: 
        # Strong Rupee (down) + Low Yields -> Bullish Bank Nifty
        # Weak Rupee (up) -> Bullish Nifty IT (Export hedge)
        
        if self.usdinr > 83.80:
            self.active_sector_bias = "IT_FAVORED"
        elif self.usdinr < 83.20:
            self.active_sector_bias = "BANK_FAVORED"
        else:
            self.active_sector_bias = "BALANCED"
            
        return self.active_sector_bias

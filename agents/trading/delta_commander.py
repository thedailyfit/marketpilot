
import logging
import random
from core.base_agent import BaseAgent

logger = logging.getLogger("DeltaAgent")

class DeltaAgent(BaseAgent):
    """
    ENGINE 14: THE DELTA COMMANDER (Strike Sniper)
    Optimizes Strike Selection based on Market Conditions.
    """
    def __init__(self):
        super().__init__("DeltaAgent")
        self.market_regime = "NORMAL" # TRENDING, GAMMA_EXPLOSIVE, CHOPPY
        
        # Simulated metrics (would connect to FeatureAgent in prod)
        self.adx = 20.0
        self.vix = 15.0

    async def on_start(self):
        logger.info("🎯 The Delta Commander (Strike Sniper) Active")

    async def on_stop(self):
        pass
        
    def _update_regime(self):
        """Simulates regime detection for Strike Selection."""
        # In prod: fetch real ADX from FeatureAgent
        self.adx = random.uniform(15, 60)
        self.vix = random.uniform(12, 28)
        
        if self.adx > 25:
            self.market_regime = "TRENDING"
        elif self.vix > 20:
             self.market_regime = "GAMMA_EXPLOSIVE"
        else:
             self.market_regime = "NORMAL"

    def get_optimal_strike_offset(self, spot_price):
        """
        Returns the optimal strike offset from Spot.
        Positive = Call Strike Target, Negative = Put Strike Target offset.
        BUT simplified: returns offset from ATM.
        0 = ATM.
        -100 = 100 pts ITM (for Call).
        """
        self._update_regime()
        
        strike_gap = 50 # Nifty strike gap
        
        if self.market_regime == "TRENDING":
            # Deep ITM for safety + high delta
            logger.info("🎯 DELTA COMMAND: High Trend (ADX > 25) -> Selecting DEEP ITM (Delta 0.7)")
            return -100 # Buy 100 pts ITM
            
        elif self.market_regime == "GAMMA_EXPLOSIVE":
            # ATM for max gamma
            logger.info("🎯 DELTA COMMAND: High Vol (VIX > 20) -> Selecting ATM (Delta 0.5)")
            return 0 # Buy ATM
            
        else:
            # Normal / Choppy -> Default Slight ITM
            return -50 # Buy 50 pts ITM

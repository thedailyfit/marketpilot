
import asyncio
import logging
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("ConstituentAgent")

class ConstituentAgent(BaseAgent):
    """
    ENGINE 4: THE PUPPET MASTER
    Tracks the 'Generals' (Top Stock Weights) to validate the 'Flag' (Index).
    """
    def __init__(self):
        super().__init__("ConstituentAgent")
        self.weights = {
            "HDFCBANK": 0.13,
            "RELIANCE": 0.10,
            "ICICIBANK": 0.07,
            "INFY": 0.06,
            "ITC": 0.04
        }
        self.last_prices = {k: 0.0 for k in self.weights.keys()}
        self.strength_score = 0.0 # -1.0 to 1.0
        self.market_status = "NEUTRAL"

    async def on_start(self):
        bus.subscribe(EventType.MARKET_DATA, self.on_tick)
        logger.info("🏗️ The Puppet Master (Constituent Correlation) Active")
        asyncio.create_task(self._simulation_loop()) # Simulating for prototype

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        # In a real scenario, we'd filter for constituent ticks here
        pass

    async def _simulation_loop(self):
        """
        Simulates constituent movement for prototype validation.
        In prod, this would be replaced by live data feeds for these 5 stocks.
        """
        while self.is_running:
            weighted_change = 0.0
            
            # Simulate random movement for each stock
            for stock, weight in self.weights.items():
                change = random.uniform(-0.5, 0.5) # % change
                # Bias: heavily correlate stocks
                if random.random() > 0.7: change = -change 
                
                weighted_change += (change * weight * 100)
            
            self.strength_score = weighted_change
            
            # Decision Logic
            prev_status = self.market_status
            if self.strength_score > 2.0:
                self.market_status = "BULLISH_PUMP"
            elif self.strength_score < -2.0:
                self.market_status = "BEARISH_DRAG"
            else:
                self.market_status = "MIXED/CHOPPY"
            
            if prev_status != self.market_status:
                logger.info(f"🏗️ PUPPET UPDATE: {self.market_status} (Score: {self.strength_score:.2f})")
                
            await asyncio.sleep(5)

    def validate_move(self, index_trend):
        """
        VETO POWER: Validates if the Index move is supported by heavyweights.
        Returns: (Allowed: bool, Reason: str)
        """
        if index_trend == "UP" and self.strength_score < -0.5:
            return False, "FAKE BREAKOUT: HDFC/RELIANCE are Red!"
        
        if index_trend == "DOWN" and self.strength_score > 0.5:
            return False, "BEAR TRAP: Banks are supporting!"
            
        return True, "CONFIRMED_BY_HEAVYWEIGHTS"

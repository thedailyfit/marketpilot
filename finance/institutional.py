import asyncio
import logging
import random
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("InstitutionalAgent")

class InstitutionalAgent(BaseAgent):
    """
    Tracks FII/DII Institutional Money Flow.
    Bias Strategy: Follow the FIIs.
    """
    
    def __init__(self):
        super().__init__("InstitutionalAgent")
        self.fii_net = 0.0
        self.dii_net = 0.0
        self.bias = "NEUTRAL"
        self.last_update = None
        
    async def on_start(self):
        logger.info("🏦 Institutional Tracker Started")
        await self._fetch_data() # Initial fetch
        asyncio.create_task(self._monitor_loop())

    async def on_stop(self):
        logger.info("🏦 Institutional Tracker Stopped")

    async def _monitor_loop(self):
        """Update data periodically."""
        while self.is_running:
            await self._fetch_data()
            await asyncio.sleep(60) # Update every minute (Simulated)

    async def _fetch_data(self):
        """
        Fetch FII/DII data.
        MVP: Simulated random flow with persistence for the day.
        """
        # In real production, this would scrape NSE website
        
        # Simulate sticky values (change rarely)
        if not self.last_update or random.random() < 0.1:
            self.fii_net = round(random.uniform(-1500, 1500), 2)
            self.dii_net = round(random.uniform(-800, 800), 2)
            self.last_update = datetime.now()
            
            self._calculate_bias()
            
            # Publish Event
            await bus.publish(EventType.ANALYSIS, {
                "type": "INSTITUTIONAL_BIAS",
                "fii": self.fii_net,
                "dii": self.dii_net,
                "bias": self.bias
            })

    def _calculate_bias(self):
        """Determine Market Bias based on Flow."""
        total_flow = self.fii_net + self.dii_net
        
        if self.fii_net > 500:
            self.bias = "BULLISH"
        elif self.fii_net < -500:
            self.bias = "BEARISH"
        else:
            if total_flow > 200:
                self.bias = "MILD_BULLISH"
            elif total_flow < -200:
                self.bias = "MILD_BEARISH"
            else:
                self.bias = "NEUTRAL"

    def get_status(self):
        return {
            "fii_net": self.fii_net,
            "dii_net": self.dii_net,
            "bias": self.bias,
            "total_flow": round(self.fii_net + self.dii_net, 2),
            "timestamp": self.last_update.isoformat() if self.last_update else None
        }

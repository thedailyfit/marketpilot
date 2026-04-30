
import asyncio
import logging
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("SectorAgent")

class SectorAgent(BaseAgent):
    """
    ENGINE 10: SECTOR SCOPE (Market Breadth)
    Tracks key sectors to determine if the 'Army is Marching Together'.
    """
    def __init__(self):
        super().__init__("SectorAgent")
        self.sectors = {
            "BANK": 0.0,
            "IT": 0.0,
            "AUTO": 0.0,
            "METAL": 0.0
        }
        self.market_breadth = "NEUTRAL"
        self.consensus_status = "WAITING"

    async def on_start(self):
        logger.info("🔬 Sector Scope (Market Breadth) Active")
        asyncio.create_task(self._sector_loop())

    async def on_stop(self):
        pass

    async def _sector_loop(self):
        """Simulates Sector Performance (real feed would fetch indices)."""
        while self.is_running:
            # Simulate Sector Random Walk
            for sec in self.sectors:
                change = random.uniform(-0.1, 0.1) # drift
                self.sectors[sec] += change
                
            # Analysis
            greens = sum(1 for v in self.sectors.values() if v > 0.05)
            reds = sum(1 for v in self.sectors.values() if v < -0.05)
            
            prev_status = self.consensus_status
            
            if greens == 4:
                self.consensus_status = "STRONG_BULLISH"
            elif reds == 4:
                self.consensus_status = "STRONG_BEARISH"
            elif greens >= 3:
                 self.consensus_status = "BULLISH_BIAS"
            elif reds >= 3:
                 self.consensus_status = "BEARISH_BIAS"
            else:
                self.consensus_status = "CHOPPY_MIXED"
                
            # Log changes
            if prev_status != self.consensus_status:
                logger.info(f"🔬 SECTOR UPDATE: {self.consensus_status} | {self.sectors}")
                
            await asyncio.sleep(5) 

    def check_alignment(self, direction):
        """
        Returns True if the trade aligns with Sector Consensus.
        """
        if self.consensus_status == "CHOPPY_MIXED":
            return False, "Sectors Mixed (Choppy Market)"
            
        if direction == "BUY":
            if "BULLISH" in self.consensus_status:
                return True, "OK"
            else:
                return False, f"Sector Mismatch (Status: {self.consensus_status})"
        
        if direction == "SELL":
             if "BEARISH" in self.consensus_status:
                return True, "OK"
             else:
                return False, f"Sector Mismatch (Status: {self.consensus_status})"
                
        return False, "Unknown Direction"

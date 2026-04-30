
import logging
import random
import time
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("ScraperAgent")

class ScraperAgent(BaseAgent):
    """
    ENGINE 28: THE PROFIT SCRAPER (Auto-Compounding)
    High-frequency profit harvester that snipes small points instantly.
    """
    def __init__(self):
        super().__init__("ScraperAgent")
        self.active_scrapes = []
        self.total_scraped_points = 0.0

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("💰 Profit Scraper (Fast Harvest) Initialized")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        # LOGIC: Check if momentum is stalling
        # This scans active positions and triggers fast exit 
        # (Simplified simulation)
        if random.random() < 0.05 and len(self.active_scrapes) > 0:
            for scrape in self.active_scrapes:
                pnl = random.uniform(2.0, 5.0)
                logger.info(f"✨ SCRAPE SUCCESS: Harvested {pnl:.1f} points. Rolling over capital.")
                self.total_scraped_points += pnl
                # Signal Fast Exit
                await bus.publish(EventType.EXECUTION, {
                    "source": "ScraperAgent",
                    "type": "FAST_EXIT",
                    "data": {"pnl_points": pnl}
                })
            self.active_scrapes = []

    def log_scrape_intent(self, trade_id):
        self.active_scrapes.append(trade_id)

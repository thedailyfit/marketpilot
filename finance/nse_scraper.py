import asyncio
import logging
import random
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("NSEScraper")

class NSEScraperAgent(BaseAgent):
    """
    Dedicated Agent to fetch EOD data from NSE India.
    Target:
    1. FII/DII Daily Net Stats.
    2. Index Futures Long/Short Ratio.
    """
    def __init__(self):
        super().__init__("NSEScraper")
        self.fii_stats = {"net": 0.0, "long_short_ratio": 0.5}
        self.dii_stats = {"net": 0.0}
        self.last_fetch = None

    async def on_start(self):
        logger.info("🦅 NSE Scraper Agent Started")
        asyncio.create_task(self._schedule_daily_scrape())

    async def on_stop(self):
        logger.info("🦅 NSE Scraper Stopped")

    async def _schedule_daily_scrape(self):
        """Run scrape loop every evening at 6:30 PM (Simulated every min for demo)."""
        while self.is_running:
            await self._scrape_nse()
            await asyncio.sleep(60) # Fast loop for Demo

    async def _scrape_nse(self):
        """
        Fetch data from NSE.
        NOTE: Real scraping requires Requests with Headers/Cookies to bypass NSE blocks.
        For MVP, we simulate the 'Parsed Data'.
        """
        try:
            # SIMULATION logic (Replace with requests.get in production)
            # FIIs usually Sell in high VIX, Buy in low VIX.
            
            # 1. FII Net Flow
            trend = random.choice([1, -1])
            fii_amt = random.uniform(500, 3000) * trend
            dii_amt = random.uniform(200, 1500) * (trend * -0.8) # DIIs usually counter FIIs
            
            self.fii_stats["net"] = round(fii_amt, 2)
            self.dii_stats["net"] = round(dii_amt, 2)
            
            # 2. Long/Short Ratio
            # > 0.6 = Bullish, < 0.4 = Bearish
            ratio = 0.5 + (0.1 * trend) + random.uniform(-0.05, 0.05)
            self.fii_stats["long_short_ratio"] = round(ratio, 2)
            
            self.last_fetch = datetime.now()
            
            # Publish Data for InstitutionalAgent to consume
            await bus.publish(EventType.ANALYSIS, {
                "source": "NSEScraper",
                "type": "INSTITUTIONAL_DATA",
                "data": {
                    "fii_net": self.fii_stats["net"],
                    "dii_net": self.dii_stats["net"],
                    "fii_ratio": self.fii_stats["long_short_ratio"]
                }
            })
            
            # logger.info(f"Scraped NSE: FII {self.fii_stats['net']} Cr | Ratio: {self.fii_stats['long_short_ratio']}")

        except Exception as e:
            logger.error(f"Scrape Failed: {e}")

    def get_stats(self):
        return {
            "fii": self.fii_stats,
            "dii": self.dii_stats,
            "timestamp": self.last_fetch.isoformat() if self.last_fetch else None
        }

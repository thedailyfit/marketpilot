import asyncio
import logging
import json
import ssl
import config
from config import TRADING_SYMBOL

# Placeholder for Upstox Streamer as we might need to mock if dependencies aren't perfect
# In a real scenario, we would import: 
# from upstox_client.feeder.portfolio_data_feed import PortfolioDataFeed
# from upstox_client.feeder.market_data_feed import MarketDataFeed

class MarketDataAgent:
    def __init__(self, output_queue):
        self.output_queue = output_queue
        self.is_running = False
        self.logger = logging.getLogger("MarketData")

    async def start(self):
        self.is_running = True
        self.logger.info("Starting Market Data Stream (Mock/Real)")
        
        # In a real implementation we would authenticate the Upstox Streamer here
        # For this skeleton, we will simulate a "Tick" generator to prove the architecture
        asyncio.create_task(self._mock_stream())

    async def _mock_stream(self):
        """Simulates incoming market data for testing the pipeline"""
        price = 19500.0
        while self.is_running:
            import random
            # Make it trend UPWARDS to trigger a BUY
            change = random.uniform(-5, 15) 
            price += change
            
            tick = {
                "type": "market_data",
                "symbol": TRADING_SYMBOL,
                "ltp": round(price, 2),
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await self.output_queue.put(tick)
            # self.logger.debug(f"Tick received: {tick['ltp']}")
            await asyncio.sleep(0.5) # Speed up: 2 ticks per second

    async def stop(self):
        self.is_running = False
        self.logger.info("Stopping Market Data Stream")

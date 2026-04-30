import asyncio
import logging
from agents.market_data import MarketDataAgent
from agents.strategy import StrategyAgent
from agents.execution import ExecutionAgent
import config

class BotEngine:
    def __init__(self):
        self.is_running = False
        self.market_agent = None
        self.strategy_agent = None
        self.execution_agent = None
        self.market_data_queue = None
        self.execution_order_queue = None
        self.logger = logging.getLogger("BotEngine")

    async def start(self, symbol=None):
        if self.is_running:
            return {"status": "Already Running"}
        
        self.is_running = True
        
        # Update Config if symbol provided
        if symbol:
            config.TRADING_SYMBOL = symbol
            self.logger.info(f"Configuration Updated: {symbol}")

        self.logger.info("Starting Bot Engine...")
        
        # Create Queues
        self.market_data_queue = asyncio.Queue()
        self.execution_order_queue = asyncio.Queue()
        
        # Instantiate Agents
        self.market_agent = MarketDataAgent(output_queue=self.market_data_queue)
        self.strategy_agent = StrategyAgent(input_queue=self.market_data_queue, execution_queue=self.execution_order_queue)
        self.execution_agent = ExecutionAgent(input_queue=self.execution_order_queue)
        
        # Start Agents
        await self.execution_agent.initialize()
        await self.execution_agent.start()
        await self.strategy_agent.start()
        
        # Start Market Data in Background Task
        asyncio.create_task(self.market_agent.start())
        
        return {"status": "Started", "symbol": config.TRADING_SYMBOL}

    async def stop(self):
        if not self.is_running:
            return {"status": "Not Running"}
        
        self.is_running = False
        self.logger.info("Stopping Bot Engine...")
        
        if self.market_agent:
            await self.market_agent.stop()
            
        return {"status": "Stopped"}

# Global Instance
engine = BotEngine()

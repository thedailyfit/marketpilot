import asyncio
from core.base_agent import BaseAgent
from agents.research.replay import ReplayAgent
from core.config_manager import sys_config

class BacktestAgent(BaseAgent):
    def __init__(self):
        super().__init__("BacktestAgent")
        self.replay_agent = ReplayAgent()
        
    async def on_start(self):
        pass

    async def run_backtest(self, symbol="NSE_FO|NIFTY"):
        self.logger.info("Initializing Backtest...")
        
        # 1. Switch Mode
        sys_config.MODE = "BACKTEST"
        
        # 2. Start Replay
        # We assume data exists for today/mock
        await self.replay_agent.run_replay(symbol, "latest", speed=1000.0)
        
        # 3. Report (Placeholder)
        self.logger.info("Backtest Finished. Check Accounting Agent for PnL.")
        
    async def on_stop(self):
        pass

import asyncio
from core.base_agent import BaseAgent
from agents.data.market_data import MarketDataAgent
from agents.analytics.feature import FeatureAgent
from agents.trading.strategy import StrategyAgent
from agents.trading.risk import RiskAgent
from agents.trading.execution import ExecutionAgent
from agents.ops.monitor import MonitorAgent
from agents.ops.compliance import ComplianceAgent
from agents.finance.accounting import AccountingAgent
from agents.research.replay import ReplayAgent
from agents.research.backtest import BacktestAgent
from agents.analytics.deep_scan import DeepScanAgent
from agents.analytics.volume import VolumeFlowAgent
from agents.analytics.prediction import PredictionEngine
from agents.analytics.sentiment import SentimentAgent
from agents.data.miner import DataMiningAgent
from agents.research.optimizer import GeneticOptimizer
from agents.finance.institutional import InstitutionalAgent
from agents.finance.oi_decoder import OIDecoderAgent
from agents.finance.nse_scraper import NSEScraperAgent # [NEW]

class SupervisorAgent(BaseAgent):
    def __init__(self):
        super().__init__("Supervisor_Kernel")
        
        # Instantiate All Agents
        self.market_agent = MarketDataAgent()
        self.feature_agent = FeatureAgent()
        self.strategy_agent = StrategyAgent()
        self.risk_agent = RiskAgent()
        self.execution_agent = ExecutionAgent()
        self.monitor_agent = MonitorAgent()
        self.compliance_agent = ComplianceAgent()
        self.accounting_agent = AccountingAgent()
        
        # Analytics Suite
        self.deep_scan_agent = DeepScanAgent()
        self.volume_agent = VolumeFlowAgent()
        self.prediction_engine = PredictionEngine()
        self.sentiment_agent = SentimentAgent()
        self.institutional_agent = InstitutionalAgent()
        self.oi_decoder = OIDecoderAgent() 
        self.nse_scraper = NSEScraperAgent() # [NEW]
        
        # Data Suite
        self.data_miner = DataMiningAgent()
        
        # Research Suite (On Demand)
        self.replay_agent = ReplayAgent()
        self.backtest_agent = BacktestAgent()
        self.optimizer = GeneticOptimizer()
        
        # Startup Order: Monitor -> Compliance -> Finance -> Execution -> Risk -> Feature -> Strategy -> Data
        # Analytics start with data flow
        self.agents = [
            self.monitor_agent,
            self.compliance_agent,
            self.accounting_agent,
            self.execution_agent,
            self.risk_agent,
            self.feature_agent,
            self.strategy_agent,
            self.market_agent,
            self.volume_agent, 
            self.deep_scan_agent,
            self.sentiment_agent,
            self.institutional_agent,
            self.oi_decoder, 
            self.nse_scraper, # [NEW]
            self.data_miner 
        ]
        # Note: Research agents (Optimizer, Backtest) are started on demand via API/CLI
        # to save resources. They are not in the main startup loop.

    async def on_start(self):
        self.logger.info("Orchestrating System Startup...")
        for agent in self.agents:
            await agent.start()
            
    async def on_stop(self):
        self.logger.info("Orchestrating System Shutdown...")
        for agent in reversed(self.agents):
            await agent.stop()
            
    def get_system_metrics(self):
        """Collects metrics from all agents."""
        # Use AccountingAgent for authoritative P&L and Balance
        finance = self.accounting_agent.get_finance_metrics()
        return finance

    def update_market_config(self, symbol: str):
        """Updates the market data agent with new symbol."""
        if self.market_agent:
            self.market_agent.update_config(symbol)

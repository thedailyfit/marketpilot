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
from agents.analytics.sector_scanner import SectorScannerAgent
from agents.finance.oi_decoder import OIDecoderAgent
from agents.finance.nse_scraper import NSEScraperAgent
from agents.trading.gamma_burst import GammaBurstAgent
from agents.trading.gamma_burst import GammaBurstAgent
from agents.analytics.patterns import PatternRecognitionAgent
from agents.research.replay import ReplayAgent
from agents.finance.constituent import ConstituentAgent
from agents.trading.tape_reader import TapeReaderAgent
from agents.analytics.fractal import FractalAgent
from agents.analytics.candle_prophet import CandleProphetAgent
from agents.trading.trap_hunter import TrapHunterAgent
from agents.finance.macro import MacroAgent
from agents.finance.sector import SectorAgent
from agents.trading.gap_tactician import GapAgent
from agents.trading.rabbit import RabbitAgent
from agents.trading.delta_commander import DeltaAgent
from agents.analytics.whale_sonar import WhaleAgent
from agents.trading.gamma_ghost import GammaGhostAgent
from agents.analytics.fii_tracker import FIITrackerAgent
from agents.analytics.premium_lab import PremiumLabAgent
from agents.analytics.neural_sentry import NeuralSentryAgent
from agents.analytics.sentiment_harvester import SentimentAgent
from agents.analytics.correlation_matrix import CorrelationAgent
from agents.trading.black_swan import BlackSwanAgent
from agents.ops.optimizer import OptimizerAgent
from agents.trading.arbitrageur import ArbitrageAgent
from agents.analytics.block_deal_sniper import BlockDealAgent
from agents.analytics.tape_master import TapeMasterAgent
from agents.trading.profit_scraper import ScraperAgent
from agents.ops.learner_agent import LearnerAgent
from agents.analytics.heatmap_agent import HeatmapAgent
from agents.analytics.hedger_agent import HedgerAgent
from agents.trading.flow_agent import FlowAgent
from agents.analytics.vpin_agent import VPINAgent
from agents.analytics.iceberg_agent import IcebergAgent
from agents.analytics.gamma_sniper import GammaSniperAgent
from agents.trading.decision_maker import DecisionMakerAgent
from agents.analytics.delta_sniper import DeltaSniperAgent
from agents.analytics.order_block import OrderBlockAgent
from agents.analytics.correlation_arbiter import CorrelationArbiterAgent
from agents.ops.mirror_mode import MirrorModeAgent

# Level-01 Orderflow Engines
from core.orderflow.footprint import footprint_engine
from core.orderflow.liquidity import liquidity_scanner

# Level-02 Intelligence Engines
from core.intelligence.regime_classifier import regime_classifier
from core.intelligence.trap_engine import trap_engine
from core.intelligence.gamma_engine import gamma_engine
from core.intelligence.iceberg_model import iceberg_model
from core.intelligence.consensus_evolution import consensus_evolution

# Level-03 Meta-Intelligence Engines
from core.meta.debate_memory import debate_memory
from core.meta.decision_explainer import decision_explainer
from core.meta.strategy_fatigue import strategy_fatigue
from core.meta.agent_evolution import agent_evolution
from core.meta.meta_risk import meta_risk

# Mode-Specific Engines
from core.modes.equity_engines import (
    support_resistance_engine, trend_engine, 
    breakout_engine, momentum_engine
)
from core.modes.futures_engines import (
    basis_engine, rollover_engine,
    contango_engine, spread_engine
)

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
        self.sector_scanner = SectorScannerAgent() # [New]
        self.institutional_agent = InstitutionalAgent()
        self.oi_decoder = OIDecoderAgent() 
        self.nse_scraper = NSEScraperAgent()
        
        # Trinity Engines
        self.gamma_agent = GammaBurstAgent()
        self.pattern_agent = PatternRecognitionAgent()
        self.replay_agent = ReplayAgent()
        
        # Phase 5 HF Engines
        self.constituent_agent = ConstituentAgent()
        self.tape_reader = TapeReaderAgent()
        
        # Phase 6 Oracle Engines
        self.fractal_agent = FractalAgent()
        self.prophet_agent = CandleProphetAgent()
        
        # Phase 7 Predator Engines
        self.trap_agent = TrapHunterAgent()
        self.macro_agent = MacroAgent()
        
        # Phase 8 Grandmaster Engines
        self.sector_agent = SectorAgent()
        self.gap_agent = GapAgent()
        
        # Phase 9 Quantum Engines
        self.rabbit_agent = RabbitAgent()
        self.delta_agent = DeltaAgent()
        self.whale_agent = WhaleAgent()
        
        # Phase 10 Matrix Engines
        self.gamma_ghost = GammaGhostAgent()
        self.fii_tracker = FIITrackerAgent()
        self.premium_lab = PremiumLabAgent()
        self.neural_sentry = NeuralSentryAgent()
        
        # Phase 11 Galaxy Engines
        self.sentiment_agent = SentimentAgent()
        self.correlation_agent = CorrelationAgent()
        self.black_swan = BlackSwanAgent()
        self.optimizer_agent = OptimizerAgent(supervisor=self)
        
        # Phase 12 Shadow Engines
        self.arbitrage_agent = ArbitrageAgent()
        self.block_sniper = BlockDealAgent()
        self.tape_master = TapeMasterAgent()
        self.scraper_agent = ScraperAgent()
        
        # Phase 13 Ghost Engines
        self.learner_agent = LearnerAgent()
        self.heatmap_agent = HeatmapAgent()
        self.hedger_agent = HedgerAgent()
        self.flow_agent = FlowAgent(supervisor=self)
        
        # Phase 14 Zenith Engines
        self.vpin_agent = VPINAgent()
        self.iceberg_agent = IcebergAgent()
        self.gamma_sniper = GammaSniperAgent()
        self.decision_maker = DecisionMakerAgent(supervisor=self)
        
        # Phase 15 Singularity Engines
        self.delta_sniper = DeltaSniperAgent()
        self.order_block = OrderBlockAgent()
        self.correlation_arbiter = CorrelationArbiterAgent()
        self.mirror_mode = MirrorModeAgent()
        
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
            self.sector_scanner, # [New]
            self.institutional_agent,
            self.oi_decoder, 
            self.nse_scraper,
            self.gamma_agent,
            self.pattern_agent,
            self.replay_agent,
            self.constituent_agent,
            self.tape_reader,
            self.fractal_agent,
            self.prophet_agent,
            self.trap_agent,
            self.macro_agent,
            self.sector_agent,
            self.gap_agent,
            self.rabbit_agent,
            self.delta_agent,
            self.whale_agent,
            self.gamma_ghost,
            self.fii_tracker,
            self.premium_lab,
            self.neural_sentry,
            self.sentiment_agent,
            self.correlation_agent,
            self.black_swan,
            self.optimizer_agent,
            self.arbitrage_agent,
            self.block_sniper,
            self.tape_master,
            self.scraper_agent,
            self.learner_agent,
            self.heatmap_agent,
            self.hedger_agent,
            self.flow_agent,
            self.vpin_agent,
            self.iceberg_agent,
            self.gamma_sniper,
            self.decision_maker,
            self.delta_sniper,
            self.order_block,
            self.correlation_arbiter,
            self.mirror_mode,
            self.data_miner
        ]
        # Note: Research agents (Optimizer, Backtest) are started on demand via API/CLI
        # to save resources. They are not in the main startup loop.

    async def on_start(self):
        self.logger.info("Orchestrating System Startup...")
        for agent in self.agents:
            await agent.start()
        
        # Level-01: Start Orderflow Engines
        await footprint_engine.on_start()
        await liquidity_scanner.on_start()
        self.logger.info("Orderflow Engines Started")
        
        # Level-02: Start Intelligence Engines
        await regime_classifier.on_start()
        await trap_engine.on_start()
        await gamma_engine.on_start()
        await iceberg_model.on_start()
        await consensus_evolution.on_start()
        self.logger.info("Intelligence Engines Started")
        
        # Level-03: Start Meta-Intelligence Engines
        await debate_memory.on_start()
        await decision_explainer.on_start()
        await strategy_fatigue.on_start()
        await agent_evolution.on_start()
        await meta_risk.on_start()
        self.logger.info("Meta-Intelligence Engines Started")
        
        # Mode-Specific Engines (automatically activate based on current mode)
        await support_resistance_engine.on_start()
        await trend_engine.on_start()
        await breakout_engine.on_start()
        await momentum_engine.on_start()
        self.logger.info("Equity Mode Engines Initialized")
        
        await basis_engine.on_start()
        await rollover_engine.on_start()
        await contango_engine.on_start()
        await spread_engine.on_start()
        self.logger.info("Futures Mode Engines Initialized")
            
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

# Global Singleton Instance
supervisor = SupervisorAgent()

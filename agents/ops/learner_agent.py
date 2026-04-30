
import logging
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("LearnerAgent")

class LearnerAgent(BaseAgent):
    """
    ENGINE 29: THE REINFORCEMENT LEARNER (Hyper-Tuner)
    Self-Evolution layer. Analyzes past outcomes to tune the swarm.
    """
    def __init__(self):
        super().__init__("LearnerAgent")
        self.engine_weights = {} # EngineName: Weight (0.5 to 2.0)
        self.performance_history = []

    async def on_start(self):
        logger.info("🤖 Reinforcement Learner (Hyper-Tuner) Active")
        # Initialize default weights
        self.engine_weights = {
            "RabbitAgent": 1.0,
            "FractalAgent": 1.0,
            "TrapHunterAgent": 1.0,
            "WhaleAgent": 1.0
        }

    async def on_stop(self):
        pass

    def tune_weights(self, last_trade_result):
        """
        Adjusts weights based on trade outcome.
        result: {'engine': 'RabbitAgent', 'pnl': 5.0}
        """
        engine = last_trade_result.get('engine')
        pnl = last_trade_result.get('pnl', 0)
        
        if engine in self.engine_weights:
            if pnl > 0:
                self.engine_weights[engine] = min(2.0, self.engine_weights[engine] + 0.05)
            else:
                self.engine_weights[engine] = max(0.5, self.engine_weights[engine] - 0.05)
            
            logger.info(f"🤖 TUNED: {engine} weight now {self.engine_weights[engine]:.2f}")
        return self.engine_weights

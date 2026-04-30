"""
ConsensusEvolution - Dynamic Agent Weight System
Adjusts Galaxy voting weights based on agent accuracy and market regime.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from collections import deque
from core.event_bus import bus, EventType


@dataclass
class AgentScore:
    """Tracking data for an agent."""
    name: str
    base_weight: float = 1.0
    accuracy: float = 0.5  # Rolling accuracy (0-1)
    predictions: int = 0
    correct: int = 0
    current_weight: float = 1.0
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "accuracy": round(self.accuracy, 2),
            "weight": round(self.current_weight, 2),
            "predictions": self.predictions
        }


class ConsensusEvolution:
    """
    Dynamically adjusts Galaxy voting weights based on:
    - Historical agent accuracy
    - Current market regime
    - Agent specialization (some agents work better in specific regimes)
    
    Flow:
    1. Record predictions from each agent
    2. After outcome known, update accuracy
    3. Apply regime-based modifiers
    4. Output adjusted weights for Galaxy voting
    """
    def __init__(self):
        self.logger = logging.getLogger("ConsensusEvolution")
        self.agents: Dict[str, AgentScore] = {}
        self.current_regime: str = "UNKNOWN"
        self.is_running = False
        
        # Regime modifiers: which agents excel in which regime
        self.regime_modifiers = {
            "TREND": {
                "Oracle": 1.3,      # Trend prediction
                "Predator": 0.7,    # Less useful in clean trends
                "Quantum": 1.1,     # Delta follows trend
                "Grandmaster": 1.2, # Macro alignment
                "Matrix": 0.9       # Institutional less relevant
            },
            "CHOP": {
                "Oracle": 0.6,      # Predictions fail in chop
                "Predator": 0.8,    # Some traps
                "Quantum": 1.4,     # Order flow key
                "Grandmaster": 0.7,
                "Matrix": 1.2
            },
            "TRAP": {
                "Oracle": 0.5,      # Predictions reverse
                "Predator": 1.6,    # Trap specialist
                "Quantum": 1.2,     # Divergence detection
                "Grandmaster": 0.8,
                "Matrix": 1.1
            },
            "PANIC": {
                "Oracle": 0.4,      # Chaos = no prediction
                "Predator": 0.6,
                "Quantum": 0.8,
                "Grandmaster": 0.5,
                "Matrix": 1.5       # Follow institutions
            }
        }
        
        # Initialize known agents
        self._init_agents()
        
    def _init_agents(self):
        """Initialize default agents."""
        for name in ["Oracle", "Predator", "Quantum", "Grandmaster", "Matrix", "Galaxy"]:
            self.agents[name] = AgentScore(name=name)
        
    async def on_start(self):
        self.logger.info("Starting Consensus Evolution Engine...")
        self.is_running = True
        bus.subscribe(EventType.REGIME_CHANGE, self._on_regime_change)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Consensus Evolution Stopped")
        
    async def _on_regime_change(self, regime_data: dict):
        """Update current regime and recalculate weights."""
        self.current_regime = regime_data.get('regime', 'UNKNOWN')
        await self._recalculate_weights()
        
    async def _recalculate_weights(self):
        """Recalculate all agent weights based on accuracy + regime."""
        modifiers = self.regime_modifiers.get(self.current_regime, {})
        
        for name, agent in self.agents.items():
            # Base = accuracy normalized (0.5 accuracy = 1.0 weight)
            accuracy_factor = agent.accuracy / 0.5
            
            # Regime modifier
            regime_mod = modifiers.get(name, 1.0)
            
            # Final weight
            agent.current_weight = agent.base_weight * accuracy_factor * regime_mod
            
            # Clamp to reasonable range
            agent.current_weight = max(0.1, min(2.0, agent.current_weight))
        
        self.logger.info(f"🎚️ WEIGHTS UPDATED for {self.current_regime}")
        await bus.publish(EventType.CONSENSUS_UPDATE, self.get_weights())
    
    def record_prediction(self, agent_name: str, prediction: str):
        """
        Record an agent's prediction.
        Prediction format: 'BULLISH', 'BEARISH', 'NEUTRAL'
        """
        if agent_name not in self.agents:
            self.agents[agent_name] = AgentScore(name=agent_name)
        self.agents[agent_name].predictions += 1
        
    def record_outcome(self, agent_name: str, was_correct: bool):
        """
        Record whether an agent's prediction was correct.
        Updates rolling accuracy with exponential decay.
        """
        if agent_name not in self.agents:
            return
            
        agent = self.agents[agent_name]
        if was_correct:
            agent.correct += 1
        
        # Exponential moving average for accuracy
        result = 1.0 if was_correct else 0.0
        agent.accuracy = 0.9 * agent.accuracy + 0.1 * result
        
        self.logger.debug(f"Outcome: {agent_name} {'✓' if was_correct else '✗'} -> {agent.accuracy:.2f}")
    
    def get_weights(self) -> Dict[str, float]:
        """Get current voting weights for all agents."""
        return {name: round(agent.current_weight, 2) for name, agent in self.agents.items()}
    
    def get_agent_stats(self) -> List[dict]:
        """Get detailed stats for all agents."""
        return [agent.to_dict() for agent in self.agents.values()]
    
    def get_weighted_vote(self, votes: Dict[str, str]) -> str:
        """
        Calculate weighted consensus from agent votes.
        votes: {agent_name: 'BULLISH'/'BEARISH'/'NEUTRAL'}
        Returns: Final consensus direction
        """
        weighted_scores = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
        
        for agent_name, vote in votes.items():
            weight = self.agents.get(agent_name, AgentScore(name=agent_name)).current_weight
            if vote in weighted_scores:
                weighted_scores[vote] += weight
        
        # Winner takes all
        consensus = max(weighted_scores, key=weighted_scores.get)
        
        self.logger.debug(f"Weighted vote: {weighted_scores} -> {consensus}")
        return consensus


# Singleton
consensus_evolution = ConsensusEvolution()

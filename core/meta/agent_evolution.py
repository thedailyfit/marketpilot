"""
AgentEvolution - Dynamic Agent Reliability Tracking
Tracks per-agent accuracy by regime, time, and adjusts voting weights.
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from core.event_bus import bus, EventType


@dataclass
class AgentProfile:
    """Complete tracking data for an agent."""
    name: str
    overall_accuracy: float = 0.5  # Rolling average (0-1)
    regime_accuracy: Dict[str, float] = field(default_factory=dict)  # {TREND: 0.72, ...}
    time_accuracy: Dict[int, float] = field(default_factory=dict)    # {9: 0.68, ...}
    recent_streak: int = 0  # +N for wins, -N for losses
    predictions: int = 0
    correct: int = 0
    reliability_score: float = 1.0
    suppressed: bool = False
    
    def to_dict(self) -> dict:
        return asdict(self)


class AgentEvolution:
    """
    Tracks and evolves agent reliability dynamically.
    
    Features:
    - Per-regime accuracy tracking
    - Per-hour accuracy tracking
    - Streak momentum
    - Dynamic suppression of unreliable agents
    """
    def __init__(self):
        self.logger = logging.getLogger("AgentEvolution")
        self.profiles: Dict[str, AgentProfile] = {}
        self.db_path = Path("data/agent_profiles.json")
        self.is_running = False
        self._load()
        self._init_defaults()
        
    def _init_defaults(self):
        """Initialize default agent profiles."""
        defaults = ["Oracle", "Predator", "Quantum", "Grandmaster", "Matrix", "Galaxy"]
        for name in defaults:
            if name not in self.profiles:
                self.profiles[name] = AgentProfile(name=name)
        
    def _load(self):
        """Load existing profiles."""
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    for name, profile_dict in data.items():
                        self.profiles[name] = AgentProfile(**profile_dict)
                self.logger.debug(f"Loaded {len(self.profiles)} agent profiles")
        except Exception as e:
            self.logger.error(f"Failed to load agent profiles: {e}")
            
    def _persist(self):
        """Save profiles to disk."""
        try:
            self.db_path.parent.mkdir(exist_ok=True)
            with open(self.db_path, 'w') as f:
                data = {name: profile.to_dict() for name, profile in self.profiles.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to persist agent profiles: {e}")
            
    async def on_start(self):
        self.logger.info("Starting Agent Evolution Engine...")
        self.is_running = True
        # Recalculate all reliability scores
        for name in self.profiles:
            self._update_reliability(name, "UNKNOWN", 12)
        
    async def on_stop(self):
        self.is_running = False
        self._persist()
        self.logger.info("Agent Evolution Engine Stopped")
        
    def record_prediction(self, agent_name: str, direction: str, regime: str):
        """Record that an agent made a prediction."""
        if agent_name not in self.profiles:
            self.profiles[agent_name] = AgentProfile(name=agent_name)
        
        self.profiles[agent_name].predictions += 1
        self._persist()
        
    async def record_outcome(
        self,
        agent_name: str,
        was_correct: bool,
        regime: str,
        hour: Optional[int] = None
    ):
        """
        Record whether an agent's prediction was correct.
        Updates rolling accuracy with exponential decay.
        """
        if agent_name not in self.profiles:
            self.profiles[agent_name] = AgentProfile(name=agent_name)
        
        profile = self.profiles[agent_name]
        hour = hour or datetime.now().hour
        
        if was_correct:
            profile.correct += 1
        
        # 1. Update overall accuracy (EMA)
        result = 1.0 if was_correct else 0.0
        profile.overall_accuracy = 0.9 * profile.overall_accuracy + 0.1 * result
        
        # 2. Update regime accuracy
        if regime not in profile.regime_accuracy:
            profile.regime_accuracy[regime] = 0.5
        profile.regime_accuracy[regime] = (
            0.85 * profile.regime_accuracy[regime] + 0.15 * result
        )
        
        # 3. Update time accuracy
        if hour not in profile.time_accuracy:
            profile.time_accuracy[hour] = 0.5
        profile.time_accuracy[hour] = (
            0.85 * profile.time_accuracy[hour] + 0.15 * result
        )
        
        # 4. Update streak
        if was_correct:
            if profile.recent_streak > 0:
                profile.recent_streak += 1
            else:
                profile.recent_streak = 1
        else:
            if profile.recent_streak < 0:
                profile.recent_streak -= 1
            else:
                profile.recent_streak = -1
        
        # 5. Update reliability score
        self._update_reliability(agent_name, regime, hour)
        
        # 6. Check for suppression
        prev_suppressed = profile.suppressed
        await self._check_suppression(agent_name)
        
        self._persist()
        self.logger.debug(
            f"Agent {agent_name}: {'✓' if was_correct else '✗'} | "
            f"Acc: {profile.overall_accuracy:.2f} | Streak: {profile.recent_streak}"
        )
        
    def _update_reliability(self, agent_name: str, regime: str, hour: int):
        """Calculate composite reliability score."""
        profile = self.profiles.get(agent_name)
        if not profile:
            return
        
        # Base = overall accuracy normalized (50% = 1.0)
        base = profile.overall_accuracy / 0.5
        
        # Regime modifier
        regime_acc = profile.regime_accuracy.get(regime, 0.5)
        regime_mod = regime_acc / 0.5
        
        # Time-of-day modifier
        hour_acc = profile.time_accuracy.get(hour, 0.5)
        time_mod = hour_acc / 0.5
        
        # Streak modifier (momentum)
        if profile.recent_streak > 3:
            streak_mod = 1.15  # Hot streak bonus
        elif profile.recent_streak < -3:
            streak_mod = 0.75  # Cold streak penalty
        else:
            streak_mod = 1.0
        
        # Composite
        reliability = base * regime_mod * time_mod * streak_mod
        
        # Clamp to [0.1, 2.0]
        profile.reliability_score = max(0.1, min(2.0, reliability))
        
    async def _check_suppression(self, agent_name: str):
        """Check if agent should be suppressed."""
        profile = self.profiles.get(agent_name)
        if not profile:
            return
        
        should_suppress = False
        reason = ""
        
        if profile.reliability_score < 0.3:
            should_suppress = True
            reason = f"Low reliability ({profile.reliability_score:.2f})"
        elif profile.recent_streak < -5:
            should_suppress = True
            reason = f"Losing streak ({profile.recent_streak})"
        elif profile.overall_accuracy < 0.35:
            should_suppress = True
            reason = f"Poor accuracy ({profile.overall_accuracy:.2f})"
        
        # State change
        if should_suppress and not profile.suppressed:
            profile.suppressed = True
            self.logger.warning(f"🔇 AGENT SUPPRESSED: {agent_name} — {reason}")
            await bus.publish(EventType.AGENT_SUPPRESSED, {
                "agent": agent_name,
                "reason": reason,
                "reliability": profile.reliability_score,
                "accuracy": profile.overall_accuracy,
                "streak": profile.recent_streak
            })
        elif not should_suppress and profile.suppressed:
            profile.suppressed = False
            self.logger.info(f"🔊 AGENT RESTORED: {agent_name}")
    
    def get_reliability(self, agent_name: str, regime: str = "UNKNOWN", hour: Optional[int] = None) -> float:
        """Get current reliability score for an agent."""
        if agent_name not in self.profiles:
            return 1.0
        
        hour = hour or datetime.now().hour
        self._update_reliability(agent_name, regime, hour)
        return self.profiles[agent_name].reliability_score
    
    def is_suppressed(self, agent_name: str) -> bool:
        """Check if agent is currently suppressed."""
        profile = self.profiles.get(agent_name)
        return profile.suppressed if profile else False
    
    def get_active_agents(self) -> List[str]:
        """Get list of non-suppressed agents."""
        return [name for name, p in self.profiles.items() if not p.suppressed]
    
    def get_profile(self, agent_name: str) -> Optional[dict]:
        """Get agent profile."""
        profile = self.profiles.get(agent_name)
        return profile.to_dict() if profile else None
    
    def get_all_profiles(self) -> Dict[str, dict]:
        """Get all agent profiles."""
        return {name: p.to_dict() for name, p in self.profiles.items()}
    
    def get_voting_weights(self, regime: str = "UNKNOWN") -> Dict[str, float]:
        """Get current voting weights for Galaxy consensus."""
        hour = datetime.now().hour
        weights = {}
        
        for name, profile in self.profiles.items():
            if profile.suppressed:
                weights[name] = 0.0
            else:
                self._update_reliability(name, regime, hour)
                weights[name] = profile.reliability_score
        
        return weights


# Singleton
agent_evolution = AgentEvolution()

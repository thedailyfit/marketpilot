"""
DebateMemory - Agent Reasoning Recorder
Records and replays agent debates for post-trade analysis.
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from core.event_bus import bus, EventType


@dataclass
class AgentVote:
    """Single agent's vote in a debate."""
    agent: str
    direction: str  # BULLISH, BEARISH, NEUTRAL
    confidence: float
    reason: str
    weight: float = 1.0


@dataclass
class DebateSnapshot:
    """Complete snapshot of an agent debate."""
    trade_id: str
    timestamp: int
    regime: str
    votes: Dict[str, dict]  # {agent_name: vote_dict}
    consensus: str
    consensus_confidence: float
    agreed_agents: List[str] = field(default_factory=list)
    dissent_agents: List[str] = field(default_factory=list)
    dissent_reasons: List[str] = field(default_factory=list)
    outcome: Optional[str] = None  # WIN, LOSS, PENDING
    pnl: Optional[float] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


class DebateMemory:
    """
    Records agent debates for every trade decision.
    Enables replay and post-analysis of reasoning.
    """
    def __init__(self):
        self.logger = logging.getLogger("DebateMemory")
        self.snapshots: Dict[str, DebateSnapshot] = {}
        self.db_path = Path("data/debate_history.json")
        self.is_running = False
        self._load()
        
    def _load(self):
        """Load existing debate history."""
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    for trade_id, snap_dict in data.items():
                        self.snapshots[trade_id] = DebateSnapshot(**snap_dict)
                self.logger.debug(f"Loaded {len(self.snapshots)} debate snapshots")
        except Exception as e:
            self.logger.error(f"Failed to load debate history: {e}")
            
    def _persist(self):
        """Save debate history to disk."""
        try:
            self.db_path.parent.mkdir(exist_ok=True)
            with open(self.db_path, 'w') as f:
                data = {tid: snap.to_dict() for tid, snap in self.snapshots.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to persist debate history: {e}")
            
    async def on_start(self):
        self.logger.info("Starting Debate Memory...")
        self.is_running = True
        
    async def on_stop(self):
        self.is_running = False
        self._persist()
        self.logger.info("Debate Memory Stopped")
        
    def record_debate(
        self,
        trade_id: str,
        votes: Dict[str, AgentVote],
        regime: str,
        consensus: str,
        confidence: float
    ) -> DebateSnapshot:
        """
        Record a new debate snapshot.
        Returns the created snapshot.
        """
        # Separate agreed vs dissenting agents
        agreed = []
        dissent = []
        dissent_reasons = []
        
        for agent_name, vote in votes.items():
            if isinstance(vote, dict):
                vote_dir = vote.get('direction', '')
                vote_reason = vote.get('reason', '')
            else:
                vote_dir = vote.direction
                vote_reason = vote.reason
                
            if vote_dir == consensus:
                agreed.append(agent_name)
            else:
                dissent.append(agent_name)
                if vote_reason:
                    dissent_reasons.append(f"{agent_name}: {vote_reason}")
        
        # Create snapshot
        snapshot = DebateSnapshot(
            trade_id=trade_id,
            timestamp=int(datetime.now().timestamp()),
            regime=regime,
            votes={k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in votes.items()},
            consensus=consensus,
            consensus_confidence=confidence,
            agreed_agents=agreed,
            dissent_agents=dissent,
            dissent_reasons=dissent_reasons
        )
        
        self.snapshots[trade_id] = snapshot
        self._persist()
        
        self.logger.info(f"📝 DEBATE RECORDED: {trade_id} | {consensus} ({confidence}%) | {len(agreed)} agreed, {len(dissent)} dissent")
        
        # Emit event
        import asyncio
        asyncio.create_task(bus.publish(EventType.DEBATE_RECORDED, snapshot.to_dict()))
        
        return snapshot
    
    def update_outcome(self, trade_id: str, outcome: str, pnl: float):
        """Update a debate with trade outcome."""
        if trade_id in self.snapshots:
            self.snapshots[trade_id].outcome = outcome
            self.snapshots[trade_id].pnl = pnl
            self._persist()
            
    def replay_debate(self, trade_id: str) -> Optional[dict]:
        """Get formatted debate for UI replay."""
        snapshot = self.snapshots.get(trade_id)
        if not snapshot:
            return None
            
        return {
            "trade_id": trade_id,
            "timestamp": snapshot.timestamp,
            "regime": snapshot.regime,
            "consensus": snapshot.consensus,
            "confidence": snapshot.consensus_confidence,
            "votes": snapshot.votes,
            "agreed": snapshot.agreed_agents,
            "dissent": snapshot.dissent_agents,
            "dissent_reasons": snapshot.dissent_reasons,
            "outcome": snapshot.outcome,
            "pnl": snapshot.pnl
        }
    
    def get_recent(self, limit: int = 10) -> List[dict]:
        """Get most recent debate snapshots."""
        sorted_snaps = sorted(
            self.snapshots.values(),
            key=lambda x: x.timestamp,
            reverse=True
        )[:limit]
        return [s.to_dict() for s in sorted_snaps]
    
    def get_dissent_rate(self) -> float:
        """Calculate average dissent rate across all debates."""
        if not self.snapshots:
            return 0.0
        total_dissent = sum(len(s.dissent_agents) for s in self.snapshots.values())
        total_agents = sum(
            len(s.agreed_agents) + len(s.dissent_agents) 
            for s in self.snapshots.values()
        )
        return total_dissent / max(total_agents, 1)


# Singleton
debate_memory = DebateMemory()

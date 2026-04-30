"""
DecisionExplainer - Plain-English Trade Reasoning
Converts agent signals into human-readable explanations.
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
from core.event_bus import bus, EventType


# Regime context descriptions
REGIME_CONTEXT = {
    "TREND": "momentum favored, follow direction",
    "CHOP": "range-bound, fade extremes",
    "TRAP": "false moves likely, wait for confirmation",
    "PANIC": "high volatility, reduce size"
}

# Risk factor descriptions
RISK_FACTORS = {
    "max_pain": "Max pain gravity may pull price",
    "vix_high": "VIX elevated — expect whipsaws",
    "trap_zone": "Near potential trap zone",
    "session_edge": "Close to session open/close",
    "low_volume": "Below average volume",
    "dissent_high": "Significant agent disagreement"
}


@dataclass
class Explanation:
    """Complete trade explanation."""
    direction: str
    confidence: float
    explanation_text: str
    why_reasons: List[str]
    risks: List[str]
    invalidation: str
    agents_agreed: List[str]
    agents_disagreed: List[str]
    regime: str
    timestamp: int
    
    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "confidence": self.confidence,
            "explanation": self.explanation_text,
            "why": self.why_reasons,
            "risks": self.risks,
            "invalidation": self.invalidation,
            "agreed": self.agents_agreed,
            "disagreed": self.agents_disagreed,
            "regime": self.regime,
            "time": self.timestamp
        }


class DecisionExplainer:
    """
    Converts agent votes and signals into plain-English explanations.
    No LLM required — uses template-based generation.
    """
    def __init__(self):
        self.logger = logging.getLogger("DecisionExplainer")
        self.last_explanation: Optional[Explanation] = None
        self.is_running = False
        
    async def on_start(self):
        self.logger.info("Starting Decision Explainer...")
        self.is_running = True
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Decision Explainer Stopped")
        
    def explain(
        self,
        votes: Dict[str, dict],
        regime: str,
        regime_confidence: float,
        context: Optional[dict] = None
    ) -> Explanation:
        """
        Generate a plain-English explanation for the current decision.
        
        Args:
            votes: {agent_name: {direction, confidence, reason, weight}}
            regime: Current market regime
            regime_confidence: Confidence in regime classification
            context: Optional additional context (vix, trap_prob, etc.)
            
        Returns:
            Explanation object with full reasoning
        """
        context = context or {}
        
        # 1. Calculate consensus
        consensus, conf = self._calc_consensus(votes)
        
        # 2. Separate agreed vs disagreed
        agreed = []
        disagreed = []
        why_reasons = []
        dissent_reasons = []
        
        # Sort by weight for importance
        sorted_votes = sorted(
            votes.items(),
            key=lambda x: x[1].get('weight', 1.0),
            reverse=True
        )
        
        for agent, vote in sorted_votes:
            vote_dir = vote.get('direction', 'NEUTRAL')
            reason = vote.get('reason', '')
            
            if vote_dir == consensus:
                agreed.append(agent)
                if reason and len(why_reasons) < 3:
                    why_reasons.append(f"{agent}: {reason}")
            else:
                disagreed.append(agent)
                if reason:
                    dissent_reasons.append(f"{agent}: {reason}")
        
        # 3. Build explanation text
        parts = []
        
        # Opening
        parts.append(f"{consensus} setup ({conf:.0f}% confidence).")
        
        # Top reasons
        if why_reasons:
            parts.append(" | ".join(why_reasons[:2]))
        
        # Regime context
        regime_desc = REGIME_CONTEXT.get(regime, "uncertain conditions")
        parts.append(f"Regime: {regime} — {regime_desc}.")
        
        # 4. Identify risks
        risks = self._identify_risks(context, regime, len(disagreed), len(agreed) + len(disagreed))
        if risks:
            parts.append(f"Risk: {risks[0]}")
        
        # 5. Invalidation condition
        invalidation = self._determine_invalidation(consensus, context)
        parts.append(f"Invalidates if: {invalidation}")
        
        explanation_text = " ".join(parts)
        
        # Create explanation object
        explanation = Explanation(
            direction=consensus,
            confidence=conf,
            explanation_text=explanation_text,
            why_reasons=why_reasons,
            risks=risks,
            invalidation=invalidation,
            agents_agreed=agreed,
            agents_disagreed=disagreed,
            regime=regime,
            timestamp=int(datetime.now().timestamp())
        )
        
        self.last_explanation = explanation
        self.logger.info(f"💬 EXPLANATION: {consensus} ({conf:.0f}%) — {len(agreed)} agreed")
        
        return explanation
    
    async def explain_and_emit(
        self,
        votes: Dict[str, dict],
        regime: str,
        regime_confidence: float,
        context: Optional[dict] = None
    ) -> Explanation:
        """Generate explanation and emit event."""
        explanation = self.explain(votes, regime, regime_confidence, context)
        await bus.publish(EventType.DECISION_EXPLAINED, explanation.to_dict())
        return explanation
    
    def _calc_consensus(self, votes: Dict[str, dict]) -> tuple:
        """Calculate weighted consensus from votes."""
        scores = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
        total_weight = 0
        
        for agent, vote in votes.items():
            direction = vote.get('direction', 'NEUTRAL')
            weight = vote.get('weight', 1.0)
            conf = vote.get('confidence', 50) / 100
            
            if direction in scores:
                scores[direction] += weight * conf
            total_weight += weight
        
        if total_weight == 0:
            return "NEUTRAL", 50.0
        
        # Winner
        consensus = max(scores, key=scores.get)
        
        # Confidence = winner score / total
        confidence = (scores[consensus] / total_weight) * 100
        
        return consensus, min(95, confidence)
    
    def _identify_risks(
        self,
        context: dict,
        regime: str,
        dissent_count: int,
        total_agents: int
    ) -> List[str]:
        """Identify and prioritize risk factors."""
        risks = []
        
        # Dissent risk
        if total_agents > 0 and dissent_count / total_agents > 0.3:
            risks.append(RISK_FACTORS["dissent_high"])
        
        # VIX risk
        if context.get('vix', 0) > 18:
            risks.append(RISK_FACTORS["vix_high"])
        
        # Trap risk
        if context.get('trap_probability', 0) > 50:
            risks.append(RISK_FACTORS["trap_zone"])
        
        # Max pain risk
        if context.get('near_max_pain', False):
            risks.append(RISK_FACTORS["max_pain"])
        
        # Session edge
        if context.get('minutes_from_open', 60) < 15:
            risks.append(RISK_FACTORS["session_edge"])
        
        return risks[:3]  # Top 3 risks
    
    def _determine_invalidation(self, consensus: str, context: dict) -> str:
        """Determine what would invalidate the trade thesis."""
        price = context.get('current_price', 0)
        atr = context.get('atr', 50)
        
        if consensus == "BULLISH":
            level = price - (atr * 0.5)
            return f"Close below {level:.0f}"
        elif consensus == "BEARISH":
            level = price + (atr * 0.5)
            return f"Close above {level:.0f}"
        else:
            return "Direction confirmed against position"
    
    def get_last(self) -> Optional[dict]:
        """Get last explanation."""
        if self.last_explanation:
            return self.last_explanation.to_dict()
        return None


# Singleton
decision_explainer = DecisionExplainer()

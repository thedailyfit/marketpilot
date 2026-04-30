"""
Market Noise Detector
Detects when market is too noisy for directional plays.
"""
import logging
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime, date


@dataclass
class NoiseAnalysis:
    """Market noise analysis result."""
    score: int              # 0-100, higher = noisier
    level: str              # LOW, MEDIUM, HIGH, EXTREME
    
    # Contributing factors
    regime: str
    atr_percentile: float
    agent_agreement: float
    chop_intensity: float
    
    recommendation: str
    restrictions: list
    
    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "level": self.level,
            "regime": self.regime,
            "atr_percentile": round(self.atr_percentile, 1),
            "agent_agreement": round(self.agent_agreement, 2),
            "recommendation": self.recommendation
        }


class MarketNoiseDetector:
    """
    Detects market noise to avoid ill-timed trades.
    
    Signals analyzed:
    - Regime (TREND vs CHOP vs PANIC)
    - ATR percentile (volatility level)
    - Agent agreement (consensus strength)
    - Chop intensity (recent whipsaw count)
    
    Output:
    - Noise score 0-100
    - Level: LOW, MEDIUM, HIGH, EXTREME
    - Recommendation for trading
    """
    
    def __init__(self):
        self.logger = logging.getLogger("MarketNoiseDetector")
        
        # Thresholds
        self.extreme_threshold = 80
        self.high_threshold = 60
        self.medium_threshold = 40
        
        # Recent whipsaws
        self.recent_signals: list = []
        self.max_signals = 20
    
    def measure(self, context: Dict) -> NoiseAnalysis:
        """
        Measure current market noise.
        
        Args:
            context: Dict with regime, atr_percentile, agent_agreement, etc.
        
        Returns:
            NoiseAnalysis with score and recommendations
        """
        regime = context.get("regime", "UNKNOWN")
        atr_percentile = context.get("atr_percentile", 50)
        agent_agreement = context.get("agent_agreement", 0.5)
        chop_signals = context.get("chop_signals", 0)
        
        score = 0
        
        # Regime contribution (0-40)
        if regime == "CHOP":
            score += 40
        elif regime == "PANIC":
            score += 35
        elif regime == "TRAP":
            score += 30
        elif regime in ["TREND_UP", "TREND_DOWN"]:
            score += 10
        else:
            score += 20  # Unknown
        
        # ATR percentile contribution (0-25)
        # High ATR with low agreement = noise
        if atr_percentile > 80:
            score += 20
        elif atr_percentile > 60:
            score += 10
        elif atr_percentile < 20:
            score += 5  # Too quiet can also be problematic
        
        # Agent agreement contribution (0-25)
        # Low agreement = conflicting signals = noise
        if agent_agreement < 0.3:
            score += 25
        elif agent_agreement < 0.5:
            score += 15
        elif agent_agreement < 0.7:
            score += 5
        # High agreement = low noise contribution
        
        # Chop intensity (0-10)
        chop_intensity = self._calculate_chop_intensity()
        score += min(10, chop_intensity * 2)
        
        # Clamp score
        score = min(100, max(0, score))
        
        # Determine level
        if score >= self.extreme_threshold:
            level = "EXTREME"
            recommendation = "AVOID TRADING - market too noisy"
            restrictions = ["NO_NEW_POSITIONS", "CLOSE_WEAK_POSITIONS"]
        elif score >= self.high_threshold:
            level = "HIGH"
            recommendation = "HIGH CONVICTION ONLY - noise elevated"
            restrictions = ["REDUCE_SIZE", "WIDER_STOPS"]
        elif score >= self.medium_threshold:
            level = "MEDIUM"
            recommendation = "TRADE WITH CAUTION"
            restrictions = ["MONITOR_CLOSELY"]
        else:
            level = "LOW"
            recommendation = "Normal trading conditions"
            restrictions = []
        
        return NoiseAnalysis(
            score=score,
            level=level,
            regime=regime,
            atr_percentile=atr_percentile,
            agent_agreement=agent_agreement,
            chop_intensity=chop_intensity,
            recommendation=recommendation,
            restrictions=restrictions
        )
    
    def record_signal(self, direction: str, was_correct: bool):
        """Record signal outcome for chop detection."""
        self.recent_signals.append({
            "timestamp": int(datetime.now().timestamp()),
            "direction": direction,
            "correct": was_correct
        })
        
        if len(self.recent_signals) > self.max_signals:
            self.recent_signals = self.recent_signals[-self.max_signals:]
    
    def _calculate_chop_intensity(self) -> float:
        """Calculate recent chop intensity from signal outcomes."""
        if len(self.recent_signals) < 5:
            return 0
        
        recent = self.recent_signals[-10:]
        
        # Count direction changes
        changes = 0
        for i in range(1, len(recent)):
            if recent[i]["direction"] != recent[i-1]["direction"]:
                changes += 1
        
        # Count incorrect signals
        incorrect = sum(1 for s in recent if not s["correct"])
        
        # Chop intensity = frequent changes + high failure rate
        intensity = (changes / len(recent)) * 50 + (incorrect / len(recent)) * 50
        
        return round(intensity, 1)
    
    def is_tradeable(self, context: Dict) -> tuple:
        """Quick check if market is tradeable."""
        analysis = self.measure(context)
        
        if analysis.level == "EXTREME":
            return False, analysis.recommendation
        
        return True, analysis.recommendation
    
    def get_session_noise_profile(self) -> Dict:
        """Get noise profile for current session."""
        now = datetime.now()
        hour = now.hour
        
        # Indian market session profiles
        if 9 <= hour < 10:
            return {
                "session": "OPENING",
                "typical_noise": "HIGH",
                "recommendation": "Wait for first 30-45 mins"
            }
        elif 10 <= hour < 14:
            return {
                "session": "CORE",
                "typical_noise": "LOW-MEDIUM",
                "recommendation": "Best trading window"
            }
        elif 14 <= hour < 15:
            return {
                "session": "LATE_AFTERNOON",
                "typical_noise": "MEDIUM",
                "recommendation": "Watch for reversals"
            }
        elif hour >= 15:
            return {
                "session": "CLOSING",
                "typical_noise": "HIGH",
                "recommendation": "Avoid new positions"
            }
        
        return {"session": "PRE_MARKET", "typical_noise": "N/A"}


# Singleton
noise_detector = MarketNoiseDetector()

"""
Market Fragility Engine
Detects pre-crash conditions using Index Proxies.
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Deque
from collections import deque
import numpy as np

@dataclass
class FragilityStatus:
    score: float       # 0 - 100 (100 = Maximum Fragility)
    is_fragile: bool   # Score > 70
    reason: str
    details: Dict

class FragilityScore:
    """
    Calculates Market Fragility based on:
    1. VIX Divergence (Price Up, VIX Up)
    2. Momentum Exhaustion (RSI Divergence) - Simulated proxy
    3. Inter-Index Divergence (Nifty vs Bank Nifty)
    """
    
    def __init__(self):
        self.logger = logging.getLogger("FragilityScore")
        
        # History buffers
        self.nifty_history: Deque[float] = deque(maxlen=50)
        self.banknifty_history: Deque[float] = deque(maxlen=50)
        self.vix_history: Deque[float] = deque(maxlen=50)
        
        # Thresholds
        self.FRAGILE_THRESHOLD = 70.0
        
    def update(self, nifty: float, banknifty: float, vix: float) -> FragilityStatus:
        """
        Update fragility components with new data.
        """
        self.nifty_history.append(nifty)
        self.banknifty_history.append(banknifty)
        self.vix_history.append(vix)
        
        if len(self.nifty_history) < 20:
            return FragilityStatus(0.0, False, "Insufficient Data", {})
            
        score = 0.0
        reasons = []
        
        # 1. VIX Divergence (30 pts)
        # Nifty making highs, VIX rising
        nifty_trend = self._get_trend(list(self.nifty_history))
        vix_trend = self._get_trend(list(self.vix_history))
        
        if nifty_trend > 0 and vix_trend > 0:
            divergence_score = 30.0
            score += divergence_score
            reasons.append("VIX Divergence (Fear rising with Price)")
        
        # 2. Inter-Index Divergence (40 pts)
        # Nifty Up, BankNifty Down (or vice versa)
        bn_trend = self._get_trend(list(self.banknifty_history))
        
        if (nifty_trend > 0 and bn_trend < 0) or (nifty_trend < 0 and bn_trend > 0):
            corr_score = 40.0
            score += corr_score
            reasons.append("Inter-Index Divergence (Leadership fracture)")
            
        # 3. Volatility Spike (30 pts)
        # VIX > 20 and rapid rise
        current_vix = self.vix_history[-1]
        vix_change = current_vix - self.vix_history[-5]
        
        if current_vix > 20.0:
            score += 15.0
            if vix_change > 1.0: # Rising fast
                score += 15.0
                reasons.append("VIX Spike (Panic)")
            else:
                reasons.append("High VIX (Fear)")
                
        # Cap score
        score = min(100.0, score)
        
        return FragilityStatus(
            score=score,
            is_fragile=score >= self.FRAGILE_THRESHOLD,
            reason=" | ".join(reasons) if reasons else "Normal Market",
            details={
                "nifty_trend": round(nifty_trend, 4),
                "vix_trend": round(vix_trend, 4),
                "vix_level": current_vix
            }
        )
        
    def _get_trend(self, data: List[float]) -> float:
        """Simple linear regression slope."""
        if len(data) < 2:
            return 0.0
        x = np.arange(len(data))
        y = np.array(data)
        slope, _ = np.polyfit(x, y, 1)
        # Normalize slope somewhat relative to price? 
        # For simplicity, returning raw slope. 
        # Positive = Up, Negative = Down
        return slope

# Singleton
fragility_engine = FragilityScore()

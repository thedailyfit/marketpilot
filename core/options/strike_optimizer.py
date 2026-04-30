"""
Strike Optimizer
Ranks strikes by risk-reward, liquidity, theta efficiency, and IV edge.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
from core.options.chain_snapshot import OptionSnapshot
from core.options.iv_surface import IVSurface


@dataclass
class StrikeScore:
    """Scored strike candidate."""
    strike: float
    expiry: str
    option_type: str
    premium: float
    
    # Component scores (0-100)
    liquidity_score: float
    risk_reward_score: float
    theta_score: float
    iv_score: float
    
    # Aggregate
    total_score: float
    grade: str  # A, B, C, D
    
    # Greeks
    delta: float
    theta: float
    vega: float
    
    # Analysis
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "strike": self.strike,
            "expiry": self.expiry,
            "type": self.option_type,
            "premium": self.premium,
            "score": round(self.total_score, 1),
            "grade": self.grade,
            "delta": self.delta,
            "theta": self.theta,
            "reasons": self.reasons,
            "warnings": self.warnings
        }


class StrikeOptimizer:
    """
    Ranks and recommends optimal strikes for options buying.
    
    Scoring Criteria:
    1. Liquidity (25%): Volume, OI, bid-ask spread
    2. Risk-Reward (35%): Distance from spot, delta exposure
    3. Theta Burden (20%): Daily decay as % of premium
    4. IV Edge (20%): Strike IV vs ATM IV
    
    Filters:
    - Minimum volume: 1000
    - Minimum OI: 5000
    - Maximum spread: 2%
    - Days to expiry: >= 2
    """
    
    def __init__(self):
        self.logger = logging.getLogger("StrikeOptimizer")
        
        # Scoring weights
        self.weights = {
            "liquidity": 0.25,
            "risk_reward": 0.35,
            "theta": 0.20,
            "iv": 0.20
        }
        
        # Filter thresholds
        self.min_volume = 1000
        self.min_oi = 5000
        self.max_spread_pct = 2.0  # %
        self.min_days_to_expiry = 2
    
    def rank_strikes(
        self,
        signal: str,  # BULLISH, BEARISH
        spot: float,
        chain: List[OptionSnapshot],
        capital: float,
        max_risk_per_trade: float = 0.02,  # 2% of capital
        iv_surface: Optional[IVSurface] = None
    ) -> List[StrikeScore]:
        """
        Rank all strikes for given signal.
        
        Args:
            signal: BULLISH or BEARISH
            spot: Current spot price
            chain: Option chain snapshot
            capital: Trading capital
            max_risk_per_trade: Max % of capital to risk
            iv_surface: Optional IV surface for IV scoring
        
        Returns:
            Top 5 strike recommendations sorted by score
        """
        option_type = "CE" if signal == "BULLISH" else "PE"
        
        # Filter chain
        candidates = self._filter_chain(chain, option_type, spot)
        
        if not candidates:
            self.logger.warning(f"No viable strikes found for {signal}")
            return []
        
        # Score each candidate
        scored = []
        for opt in candidates:
            score = self._score_strike(opt, spot, iv_surface)
            scored.append(score)
        
        # Sort by total score
        scored.sort(key=lambda x: x.total_score, reverse=True)
        
        # Return top 5
        return scored[:5]
    
    def _filter_chain(
        self,
        chain: List[OptionSnapshot],
        option_type: str,
        spot: float
    ) -> List[OptionSnapshot]:
        """Filter chain by liquidity and viability."""
        filtered = []
        
        for opt in chain:
            # Type filter
            if opt.option_type != option_type:
                continue
            
            # Liquidity filters
            if opt.volume < self.min_volume:
                continue
            if opt.oi < self.min_oi:
                continue
            
            # Spread filter
            if opt.bid > 0 and opt.ask > 0:
                spread_pct = (opt.ask - opt.bid) / opt.ltp * 100
                if spread_pct > self.max_spread_pct:
                    continue
            
            # Days to expiry filter
            try:
                expiry_date = datetime.strptime(opt.expiry, '%Y-%m-%d').date()
                days_left = (expiry_date - date.today()).days
                if days_left < self.min_days_to_expiry:
                    continue
            except:
                continue
            
            # Distance filter: Only consider strikes within 5% of spot
            distance_pct = abs(opt.strike - spot) / spot * 100
            if distance_pct > 5:
                continue
            
            filtered.append(opt)
        
        return filtered
    
    def _score_strike(
        self,
        opt: OptionSnapshot,
        spot: float,
        iv_surface: Optional[IVSurface]
    ) -> StrikeScore:
        """Calculate comprehensive score for a strike."""
        
        # 1. Liquidity Score (0-100)
        liquidity = self._liquidity_score(opt)
        
        # 2. Risk-Reward Score (0-100)
        risk_reward = self._risk_reward_score(opt, spot)
        
        # 3. Theta Score (0-100) - Higher = less theta burden
        theta = self._theta_score(opt)
        
        # 4. IV Score (0-100)
        iv = self._iv_score(opt, iv_surface)
        
        # Weighted total
        total = (
            liquidity * self.weights["liquidity"] +
            risk_reward * self.weights["risk_reward"] +
            theta * self.weights["theta"] +
            iv * self.weights["iv"]
        )
        
        # Grade
        if total >= 80:
            grade = "A"
        elif total >= 65:
            grade = "B"
        elif total >= 50:
            grade = "C"
        else:
            grade = "D"
        
        # Generate reasons and warnings
        reasons, warnings = self._generate_analysis(opt, spot, liquidity, risk_reward, theta, iv)
        
        return StrikeScore(
            strike=opt.strike,
            expiry=opt.expiry,
            option_type=opt.option_type,
            premium=opt.ltp,
            liquidity_score=liquidity,
            risk_reward_score=risk_reward,
            theta_score=theta,
            iv_score=iv,
            total_score=total,
            grade=grade,
            delta=opt.delta,
            theta=opt.theta,
            vega=opt.vega,
            reasons=reasons,
            warnings=warnings
        )
    
    def _liquidity_score(self, opt: OptionSnapshot) -> float:
        """Score based on volume, OI, and spread."""
        score = 0
        
        # Volume score (0-40)
        if opt.volume >= 50000:
            score += 40
        elif opt.volume >= 20000:
            score += 35
        elif opt.volume >= 10000:
            score += 30
        elif opt.volume >= 5000:
            score += 25
        else:
            score += 15
        
        # OI score (0-30)
        if opt.oi >= 100000:
            score += 30
        elif opt.oi >= 50000:
            score += 25
        elif opt.oi >= 20000:
            score += 20
        else:
            score += 10
        
        # Spread score (0-30)
        if opt.bid > 0 and opt.ask > 0:
            spread_pct = (opt.ask - opt.bid) / opt.ltp * 100
            if spread_pct < 0.3:
                score += 30
            elif spread_pct < 0.5:
                score += 25
            elif spread_pct < 1.0:
                score += 20
            elif spread_pct < 1.5:
                score += 15
            else:
                score += 5
        else:
            score += 10  # Unknown spread
        
        return min(100, score)
    
    def _risk_reward_score(self, opt: OptionSnapshot, spot: float) -> float:
        """Score based on moneyness and delta."""
        score = 0
        
        # Distance from spot
        distance_pct = abs(opt.strike - spot) / spot * 100
        
        # Sweet spot: 1-2% OTM for directional trades
        if 0.8 <= distance_pct <= 2.0:
            score += 50  # Optimal range
        elif 0.3 <= distance_pct <= 0.8:
            score += 40  # Slightly ATM, more premium
        elif 2.0 < distance_pct <= 3.0:
            score += 35  # Moderate OTM
        elif distance_pct < 0.3:
            score += 30  # ATM, expensive
        else:
            score += 20  # Far OTM
        
        # Delta score (0.3-0.5 optimal for directional)
        abs_delta = abs(opt.delta)
        if 0.35 <= abs_delta <= 0.50:
            score += 50  # Optimal delta
        elif 0.25 <= abs_delta <= 0.35:
            score += 40
        elif 0.50 < abs_delta <= 0.65:
            score += 35  # ITM
        elif 0.15 <= abs_delta < 0.25:
            score += 25  # Low delta OTM
        else:
            score += 15
        
        return min(100, score)
    
    def _theta_score(self, opt: OptionSnapshot) -> float:
        """Score based on theta burden (lower theta = higher score)."""
        # Theta as % of premium
        if opt.ltp <= 0:
            return 50
        
        theta_pct = abs(opt.theta) / opt.ltp * 100
        
        if theta_pct < 2:
            return 100  # Minimal theta
        elif theta_pct < 4:
            return 85
        elif theta_pct < 6:
            return 70
        elif theta_pct < 8:
            return 55
        elif theta_pct < 10:
            return 40
        else:
            return 20  # High theta burden
    
    def _iv_score(self, opt: OptionSnapshot, iv_surface: Optional[IVSurface]) -> float:
        """Score based on IV relative to ATM."""
        if not iv_surface:
            return 50  # Neutral if no surface
        
        atm_iv = iv_surface.atm_iv
        if atm_iv <= 0:
            return 50
        
        # Strike IV vs ATM
        iv_ratio = opt.iv / atm_iv
        
        # Lower IV than ATM is better for buying
        if iv_ratio < 0.95:
            return 90  # IV below ATM, good deal
        elif iv_ratio < 1.0:
            return 75
        elif iv_ratio < 1.05:
            return 60  # Slight premium
        elif iv_ratio < 1.10:
            return 45
        else:
            return 30  # High IV premium
    
    def _generate_analysis(
        self,
        opt: OptionSnapshot,
        spot: float,
        liquidity: float,
        risk_reward: float,
        theta: float,
        iv: float
    ) -> Tuple[List[str], List[str]]:
        """Generate human-readable analysis."""
        reasons = []
        warnings = []
        
        # Liquidity
        if liquidity >= 80:
            reasons.append("Excellent liquidity")
        elif liquidity >= 60:
            reasons.append("Good liquidity")
        elif liquidity < 50:
            warnings.append("Limited liquidity - watch slippage")
        
        # Risk-Reward
        distance_pct = abs(opt.strike - spot) / spot * 100
        if 0.8 <= distance_pct <= 2.0:
            reasons.append(f"Optimal distance from ATM ({distance_pct:.1f}%)")
        elif distance_pct > 3:
            warnings.append(f"Far OTM ({distance_pct:.1f}%) - lower probability")
        
        # Delta
        abs_delta = abs(opt.delta)
        if 0.35 <= abs_delta <= 0.50:
            reasons.append(f"Balanced delta ({abs_delta:.2f})")
        elif abs_delta < 0.25:
            warnings.append(f"Low delta ({abs_delta:.2f}) - needs large move")
        
        # Theta
        if theta >= 70:
            reasons.append("Low theta burden")
        elif theta < 40:
            warnings.append("High theta decay - short holding period")
        
        # IV
        if iv >= 75:
            reasons.append("IV below ATM - good value")
        elif iv < 40:
            warnings.append("High IV premium - expensive")
        
        return reasons, warnings
    
    def get_best_strike(
        self,
        signal: str,
        spot: float,
        chain: List[OptionSnapshot],
        capital: float
    ) -> Optional[StrikeScore]:
        """Get single best strike recommendation."""
        ranked = self.rank_strikes(signal, spot, chain, capital)
        return ranked[0] if ranked else None
    
    def compare_strikes(
        self,
        strikes: List[StrikeScore]
    ) -> Dict[str, any]:
        """Generate comparison summary for UI."""
        if not strikes:
            return {"strikes": [], "best": None}
        
        return {
            "strikes": [s.to_dict() for s in strikes],
            "best": strikes[0].to_dict(),
            "comparison": {
                "highest_liquidity": max(strikes, key=lambda x: x.liquidity_score).strike,
                "best_risk_reward": max(strikes, key=lambda x: x.risk_reward_score).strike,
                "lowest_theta": max(strikes, key=lambda x: x.theta_score).strike,
                "best_iv_value": max(strikes, key=lambda x: x.iv_score).strike
            }
        }


# Singleton
strike_optimizer = StrikeOptimizer()

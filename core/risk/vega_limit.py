"""
Vega Exposure Limit
Protects against IV crush by limiting vega exposure.
"""
import logging
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class VegaExposureStatus:
    """Current vega exposure status."""
    max_vega: float          # Max allowed vega
    current_vega: float      # Current portfolio vega
    remaining_capacity: float
    utilization_pct: float
    
    iv_crush_10_impact: float  # P&L if IV drops 10%
    iv_crush_20_impact: float  # P&L if IV drops 20%
    
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    
    def to_dict(self) -> dict:
        return {
            "max_vega": round(self.max_vega, 2),
            "current_vega": round(self.current_vega, 2),
            "remaining": round(self.remaining_capacity, 2),
            "utilization": round(self.utilization_pct, 1),
            "iv_crush_10": round(self.iv_crush_10_impact, 2),
            "iv_crush_20": round(self.iv_crush_20_impact, 2),
            "risk_level": self.risk_level
        }


class VegaExposureLimit:
    """
    Limits vega exposure to protect against IV crush.
    
    Purpose:
    - Prevent catastrophic losses from IV crush
    - Force awareness of vega risk
    - Enable informed position sizing
    
    Calculation:
    - Vega impact = Total Vega × IV change in %
    - 10% IV crush on ₹50 vega = ₹500 loss
    
    Limits:
    - Max vega as % of capital (default 2%)
    - Warning at 1.5%
    - Critical at 3%
    """
    
    def __init__(self, capital: float = 500000, max_vega_pct: float = 0.02):
        self.logger = logging.getLogger("VegaExposureLimit")
        self.capital = capital
        self.max_vega_pct = max_vega_pct  # 2% default
        self.current_vega = 0.0
    
    @property
    def max_vega(self) -> float:
        """Calculate max allowed vega."""
        return self.capital * self.max_vega_pct
    
    def update_capital(self, capital: float):
        """Update capital for vega calculation."""
        self.capital = capital
    
    def update_current_vega(self, vega: float):
        """Update current portfolio vega."""
        self.current_vega = abs(vega)
    
    def get_status(self) -> VegaExposureStatus:
        """Get current vega exposure status."""
        max_v = self.max_vega
        remaining = max(0, max_v - self.current_vega)
        utilization = (self.current_vega / max_v * 100) if max_v > 0 else 0
        
        # Calculate IV crush impacts
        iv_crush_10 = self.current_vega * 10  # 10% IV drop
        iv_crush_20 = self.current_vega * 20  # 20% IV drop
        
        # Determine risk level
        if utilization >= 150:
            risk_level = "CRITICAL"
        elif utilization >= 100:
            risk_level = "HIGH"
        elif utilization >= 75:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return VegaExposureStatus(
            max_vega=max_v,
            current_vega=self.current_vega,
            remaining_capacity=remaining,
            utilization_pct=utilization,
            iv_crush_10_impact=iv_crush_10,
            iv_crush_20_impact=iv_crush_20,
            risk_level=risk_level
        )
    
    def check(
        self,
        new_vega: float
    ) -> Dict[str, any]:
        """
        Check if new position can be added within vega limits.
        
        Args:
            new_vega: Vega of new position
        
        Returns:
            Dict with allowed, reason, and risk analysis
        """
        new_v = abs(new_vega)
        projected = self.current_vega + new_v
        max_v = self.max_vega
        
        if projected > max_v:
            # Estimate crush impact
            crush_loss = projected * 10  # 10% IV crush
            crush_pct = crush_loss / self.capital * 100 if self.capital > 0 else 0
            
            return {
                "allowed": False,
                "reason": f"Vega limit exceeded: {projected:.0f} > {max_v:.0f}",
                "current_vega": round(self.current_vega, 2),
                "new_vega": round(new_v, 2),
                "projected": round(projected, 2),
                "max_allowed": round(max_v, 2),
                "iv_crush_risk": f"10% IV crush = ₹{crush_loss:.0f} ({crush_pct:.1f}% of capital)"
            }
        
        # Warning zone
        if projected > max_v * 0.75:
            crush_loss = projected * 10
            return {
                "allowed": True,
                "warning": "High vega exposure - IV crush risk elevated",
                "iv_crush_10": f"₹{crush_loss:.0f} potential loss",
                "recommendation": "Consider reducing or hedging vega"
            }
        
        return {
            "allowed": True,
            "remaining_capacity": round(max_v - projected, 2)
        }
    
    def estimate_crush_impact(
        self,
        vega: float,
        iv_drop_pct: float = 10
    ) -> Dict[str, float]:
        """
        Estimate impact of IV crush.
        
        Args:
            vega: Total vega exposure
            iv_drop_pct: Expected IV drop (e.g., 10 for 10%)
        
        Returns:
            Loss estimates
        """
        loss = abs(vega) * iv_drop_pct
        loss_pct = (loss / self.capital * 100) if self.capital > 0 else 0
        
        severity = "MINOR"
        if loss_pct > 10:
            severity = "CATASTROPHIC"
        elif loss_pct > 5:
            severity = "SEVERE"
        elif loss_pct > 2:
            severity = "SIGNIFICANT"
        elif loss_pct > 1:
            severity = "MODERATE"
        
        return {
            "iv_drop": f"{iv_drop_pct}%",
            "estimated_loss": round(loss, 2),
            "loss_pct": round(loss_pct, 2),
            "severity": severity,
            "recommendation": self._crush_recommendation(severity)
        }
    
    def _crush_recommendation(self, severity: str) -> str:
        """Generate recommendation based on crush severity."""
        recommendations = {
            "MINOR": "Exposure acceptable",
            "MODERATE": "Monitor IV levels closely",
            "SIGNIFICANT": "Consider reducing vega exposure",
            "SEVERE": "Strongly recommend hedging or reducing positions",
            "CATASTROPHIC": "URGENT: Reduce vega exposure immediately"
        }
        return recommendations.get(severity, "Review positions")
    
    def calculate_hedge_needed(self) -> Dict[str, any]:
        """Calculate vega hedge needed for neutrality."""
        status = self.get_status()
        
        if status.risk_level in ["LOW", "MEDIUM"]:
            return {
                "hedge_needed": False,
                "reason": "Vega exposure within acceptable limits"
            }
        
        return {
            "hedge_needed": True,
            "vega_to_hedge": round(self.current_vega, 2),
            "options": [
                "Sell OTM options to reduce vega",
                "Close some long positions",
                "Buy calendar spreads (short front-month)"
            ]
        }


# Singleton
vega_exposure_limit = VegaExposureLimit()

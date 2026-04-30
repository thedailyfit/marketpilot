"""
Theta Decay Curve
Models non-linear theta decay for options based on time and moneyness.
"""
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, date, timedelta
import math


@dataclass
class DecayPoint:
    """Single point on decay curve."""
    day: int              # Days from now
    days_to_expiry: int   # Remaining days
    decay_rate: float     # Daily decay as % of premium
    projected_price: float
    cumulative_decay: float


class ThetaDecayCurve:
    """
    Models non-linear theta decay for options.
    
    Key insights:
    - ATM options decay fastest in final 7 days
    - OTM options decay slower initially, then accelerate
    - ITM options have minimal time value decay
    - Weekend theta is priced in during Friday trading
    
    This engine provides:
    - Decay rate by moneyness and days to expiry
    - Projected premium curve over time
    - Optimal holding period estimation
    - Weekend theta adjustment
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ThetaDecayCurve")
    
    def get_decay_rate(
        self,
        days_to_expiry: int,
        moneyness: float
    ) -> float:
        """
        Get daily theta decay as percentage of premium.
        
        Args:
            days_to_expiry: Days until expiry
            moneyness: Strike / Spot ratio
                       < 1 = ITM for calls, OTM for puts
                       = 1 = ATM
                       > 1 = OTM for calls, ITM for puts
        
        Returns:
            Daily decay rate (e.g., 0.08 = 8% of premium per day)
        """
        # ATM options (0.97 - 1.03)
        if 0.97 <= moneyness <= 1.03:
            return self._atm_decay_rate(days_to_expiry)
        
        # OTM options
        if moneyness > 1.03 or moneyness < 0.97:
            return self._otm_decay_rate(days_to_expiry, abs(1 - moneyness))
        
        return 0.03  # Default
    
    def _atm_decay_rate(self, days_to_expiry: int) -> float:
        """
        ATM decay rate follows sqrt(t) pattern.
        Accelerates dramatically in last week.
        """
        if days_to_expiry <= 1:
            return 0.30  # 30% final day
        elif days_to_expiry <= 3:
            return 0.15  # 15% per day
        elif days_to_expiry <= 7:
            return 0.08  # 8% per day
        elif days_to_expiry <= 14:
            return 0.04  # 4% per day
        elif days_to_expiry <= 30:
            return 0.02  # 2% per day
        else:
            return 0.01  # 1% per day
    
    def _otm_decay_rate(self, days_to_expiry: int, otm_distance: float) -> float:
        """
        OTM decay is slower initially but accelerates.
        Far OTM options can go to zero rapidly near expiry.
        """
        # Base rate (slower than ATM)
        base = self._atm_decay_rate(days_to_expiry) * 0.7
        
        # OTM acceleration factor
        if days_to_expiry <= 3 and otm_distance > 0.03:
            # Far OTM options in last 3 days decay very fast
            return min(0.50, base * (1 + otm_distance * 10))
        
        # Deeper OTM = slower decay (less to decay)
        return base * (1 - otm_distance * 2)
    
    def project_decay(
        self,
        premium: float,
        days_to_expiry: int,
        moneyness: float,
        spot: float,
        strike: float
    ) -> List[DecayPoint]:
        """
        Project premium decay curve over remaining life.
        
        Args:
            premium: Current option premium
            days_to_expiry: Days until expiry
            moneyness: Strike/Spot ratio
            spot: Current spot price
            strike: Strike price
        
        Returns:
            List of DecayPoint for each day
        """
        curve = []
        current_premium = premium
        cumulative_decay = 0
        
        for day in range(days_to_expiry + 1):
            days_left = days_to_expiry - day
            
            if days_left <= 0:
                # At expiry - only intrinsic value
                intrinsic = max(0, spot - strike) if moneyness < 1 else max(0, strike - spot)
                curve.append(DecayPoint(
                    day=day,
                    days_to_expiry=0,
                    decay_rate=1.0,
                    projected_price=intrinsic,
                    cumulative_decay=premium - intrinsic
                ))
                break
            
            decay_rate = self.get_decay_rate(days_left, moneyness)
            decay_amount = current_premium * decay_rate
            current_premium = max(0, current_premium - decay_amount)
            cumulative_decay += decay_amount
            
            curve.append(DecayPoint(
                day=day,
                days_to_expiry=days_left,
                decay_rate=decay_rate,
                projected_price=round(current_premium, 2),
                cumulative_decay=round(cumulative_decay, 2)
            ))
        
        return curve
    
    def estimate_optimal_hold_period(
        self,
        days_to_expiry: int,
        moneyness: float
    ) -> Dict[str, any]:
        """
        Estimate optimal holding period before theta becomes destructive.
        
        Returns period where theta decay is still manageable.
        """
        if days_to_expiry > 14:
            # Far from expiry - can hold longer
            max_hold = days_to_expiry - 7  # Exit 7 days before expiry
            recommendation = "Can hold position, monitor 7 days before expiry"
        elif days_to_expiry > 7:
            # Medium term
            max_hold = days_to_expiry - 3  # Exit 3 days before
            recommendation = "Theta starting to accelerate, exit 3 days before expiry"
        elif days_to_expiry > 3:
            # Near term - theta aggressive
            max_hold = 1  # Only hold overnight if strong conviction
            recommendation = "High theta zone - intraday trades preferred"
        else:
            # Final days - theta destruction zone
            max_hold = 0
            recommendation = "Theta destruction zone - avoid holding overnight"
        
        # ATM has faster decay
        if 0.98 <= moneyness <= 1.02:
            max_hold = max(0, max_hold - 1)
            recommendation += " (ATM: reduce hold time)"
        
        return {
            "max_hold_days": max_hold,
            "recommendation": recommendation,
            "theta_zone": self._classify_theta_zone(days_to_expiry),
            "daily_decay_estimate": f"{self.get_decay_rate(days_to_expiry, moneyness)*100:.0f}%"
        }
    
    def _classify_theta_zone(self, days_to_expiry: int) -> str:
        """Classify theta severity zone."""
        if days_to_expiry > 14:
            return "GREEN"  # Low theta
        elif days_to_expiry > 7:
            return "YELLOW"  # Medium theta
        elif days_to_expiry > 3:
            return "ORANGE"  # High theta
        else:
            return "RED"  # Extreme theta
    
    def calculate_weekend_theta(
        self,
        premium: float,
        days_to_expiry: int,
        moneyness: float,
        is_friday: bool = False
    ) -> Dict[str, float]:
        """
        Calculate weekend theta impact.
        
        Weekend theta is typically priced in during Friday trading.
        This estimates the expected decay from Friday close to Monday open.
        """
        if not is_friday:
            return {"weekend_theta": 0, "adjusted_premium": premium}
        
        # Friday close to Monday = 3 calendar days, but 1 trading day
        # Market typically prices ~2 days of theta on Friday
        
        daily_rate = self.get_decay_rate(days_to_expiry, moneyness)
        weekend_theta = premium * daily_rate * 2  # 2 days worth
        
        return {
            "weekend_theta": round(weekend_theta, 2),
            "weekend_theta_pct": round(daily_rate * 2 * 100, 1),
            "adjusted_premium": round(premium - weekend_theta, 2),
            "recommendation": "Avoid holding long options over weekend" if daily_rate > 0.05 else "Weekend hold acceptable"
        }
    
    def get_decay_summary(
        self,
        premium: float,
        days_to_expiry: int,
        moneyness: float
    ) -> Dict[str, any]:
        """
        Get comprehensive theta decay summary.
        """
        daily_rate = self.get_decay_rate(days_to_expiry, moneyness)
        zone = self._classify_theta_zone(days_to_expiry)
        
        # Project next 5 days or until expiry
        projection_days = min(5, days_to_expiry)
        projected_values = []
        current = premium
        
        for d in range(1, projection_days + 1):
            rate = self.get_decay_rate(days_to_expiry - d, moneyness)
            current = current * (1 - rate)
            projected_values.append(round(current, 2))
        
        # Calculate cumulative decay over projection
        total_decay = premium - current
        total_decay_pct = (total_decay / premium * 100) if premium > 0 else 0
        
        return {
            "current_premium": premium,
            "days_to_expiry": days_to_expiry,
            "moneyness": round(moneyness, 3),
            "theta_zone": zone,
            "daily_decay_rate": f"{daily_rate * 100:.1f}%",
            "daily_decay_amount": round(premium * daily_rate, 2),
            "projection": projected_values,
            "5_day_decay": f"{total_decay_pct:.1f}%",
            "5_day_decay_amount": round(total_decay, 2),
            "hold_recommendation": self.estimate_optimal_hold_period(days_to_expiry, moneyness)["recommendation"]
        }


# Singleton
theta_decay_curve = ThetaDecayCurve()

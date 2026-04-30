"""
Expiry Evaluator
Decides between weekly and monthly expiry based on signal, IV, and theta.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from core.options.iv_surface import IVSurface


@dataclass
class ExpiryRecommendation:
    """Expiry evaluation result."""
    recommended_expiry: str  # ISO date
    expiry_type: str         # WEEKLY, MONTHLY
    days_to_expiry: int
    
    # Reasoning
    reason: str
    factors: Dict[str, str]
    
    # Risk analysis
    theta_zone: str
    iv_consideration: str
    
    # Alternatives
    alternative_expiry: Optional[str] = None
    alternative_reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "expiry": self.recommended_expiry,
            "type": self.expiry_type,
            "days": self.days_to_expiry,
            "reason": self.reason,
            "factors": self.factors,
            "theta_zone": self.theta_zone,
            "alternative": self.alternative_expiry
        }


class ExpiryEvaluator:
    """
    Evaluates and recommends optimal expiry for options trades.
    
    Decision Factors:
    1. Signal Horizon: INTRADAY vs SWING vs POSITIONAL
    2. IV Percentile: High IV → Consider monthly, Low IV → Weekly leverage
    3. Days to Weekly: Avoid < 2 days
    4. Event Calendar: Earnings, RBI, F&O expiry
    
    Rules:
    - INTRADAY → Weekly (if >= 2 days left)
    - SWING (2-5 days) → Weekly if >= 4 days, else monthly
    - POSITIONAL (5+ days) → Monthly
    - High IV (>70%) → Monthly (for theta decay in favor)
    - Low IV (<30%) → Weekly (for leverage)
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ExpiryEvaluator")
        
        # Weekly expiry (Thursday for NIFTY/BANKNIFTY)
        self.weekly_expiry_day = 3  # Thursday = 3 (Monday=0)
    
    def evaluate(
        self,
        signal_horizon: str,  # INTRADAY, SWING, POSITIONAL
        current_date: Optional[date] = None,
        iv_surface: Optional[IVSurface] = None,
        symbol: str = "NIFTY"
    ) -> ExpiryRecommendation:
        """
        Evaluate and recommend expiry.
        
        Args:
            signal_horizon: Trade duration expectation
            current_date: Today's date (defaults to now)
            iv_surface: Optional IV surface for IV-based decisions
            symbol: Underlying symbol
        
        Returns:
            ExpiryRecommendation with analysis
        """
        if current_date is None:
            current_date = date.today()
        
        # Get expiry dates
        weekly_expiry = self._get_weekly_expiry(current_date)
        monthly_expiry = self._get_monthly_expiry(current_date)
        
        days_to_weekly = (weekly_expiry - current_date).days
        days_to_monthly = (monthly_expiry - current_date).days
        
        # Get IV percentile
        iv_percentile = iv_surface.iv_percentile if iv_surface else 50
        iv_regime = iv_surface.regime if iv_surface else "NORMAL"
        
        # Apply decision rules
        factors = {}
        
        # Rule 1: Never buy weekly with < 2 days to expiry
        if days_to_weekly < 2:
            factors["weekly_viable"] = "NO - Less than 2 days"
            weekly_viable = False
        else:
            factors["weekly_viable"] = f"YES - {days_to_weekly} days left"
            weekly_viable = True
        
        # Rule 2: INTRADAY → Weekly (if viable)
        if signal_horizon == "INTRADAY":
            if weekly_viable:
                return self._recommend_weekly(
                    weekly_expiry, days_to_weekly,
                    "Intraday signal — weekly provides optimal leverage",
                    factors, iv_percentile, monthly_expiry
                )
            else:
                return self._recommend_monthly(
                    monthly_expiry, days_to_monthly,
                    "Weekly too close to expiry — monthly safer for intraday",
                    factors, iv_percentile
                )
        
        # Rule 3: High IV → Monthly (avoid IV crush)
        if iv_percentile > 70 or iv_regime == "CRUSH_RISK":
            factors["iv_consideration"] = f"HIGH IV ({iv_percentile:.0f}%) - Monthly preferred"
            return self._recommend_monthly(
                monthly_expiry, days_to_monthly,
                "High IV environment — monthly for theta protection",
                factors, iv_percentile
            )
        
        # Rule 4: Low IV → Weekly for leverage
        if iv_percentile < 30 or iv_regime in ["LOW_IV", "EXPANSION_LIKELY"]:
            if weekly_viable:
                factors["iv_consideration"] = f"LOW IV ({iv_percentile:.0f}%) - Weekly for leverage"
                return self._recommend_weekly(
                    weekly_expiry, days_to_weekly,
                    "Low IV — weekly provides better leverage for directional move",
                    factors, iv_percentile, monthly_expiry
                )
        
        # Rule 5: SWING → Weekly if 4+ days, else monthly
        if signal_horizon == "SWING":
            if weekly_viable and days_to_weekly >= 4:
                factors["swing_analysis"] = f"Weekly has {days_to_weekly} days — sufficient for swing"
                return self._recommend_weekly(
                    weekly_expiry, days_to_weekly,
                    "Swing trade — weekly with adequate days remaining",
                    factors, iv_percentile, monthly_expiry
                )
            else:
                factors["swing_analysis"] = f"Weekly only {days_to_weekly} days — insufficient for swing"
                return self._recommend_monthly(
                    monthly_expiry, days_to_monthly,
                    "Swing trade — monthly for safer holding period",
                    factors, iv_percentile
                )
        
        # Rule 6: POSITIONAL → Monthly
        if signal_horizon == "POSITIONAL":
            factors["positional"] = "Multi-day holding — monthly required"
            return self._recommend_monthly(
                monthly_expiry, days_to_monthly,
                "Positional trade — monthly for theta protection",
                factors, iv_percentile
            )
        
        # Default: Monthly (safer choice)
        return self._recommend_monthly(
            monthly_expiry, days_to_monthly,
            "Default — monthly for balanced risk",
            factors, iv_percentile
        )
    
    def _recommend_weekly(
        self,
        expiry: date,
        days: int,
        reason: str,
        factors: Dict,
        iv_percentile: float,
        monthly_alt: date
    ) -> ExpiryRecommendation:
        """Create weekly recommendation."""
        theta_zone = self._get_theta_zone(days)
        
        return ExpiryRecommendation(
            recommended_expiry=expiry.isoformat(),
            expiry_type="WEEKLY",
            days_to_expiry=days,
            reason=reason,
            factors=factors,
            theta_zone=theta_zone,
            iv_consideration=f"IV at {iv_percentile:.0f}th percentile",
            alternative_expiry=monthly_alt.isoformat(),
            alternative_reason="Monthly offers more time, less theta risk"
        )
    
    def _recommend_monthly(
        self,
        expiry: date,
        days: int,
        reason: str,
        factors: Dict,
        iv_percentile: float
    ) -> ExpiryRecommendation:
        """Create monthly recommendation."""
        theta_zone = self._get_theta_zone(days)
        
        return ExpiryRecommendation(
            recommended_expiry=expiry.isoformat(),
            expiry_type="MONTHLY",
            days_to_expiry=days,
            reason=reason,
            factors=factors,
            theta_zone=theta_zone,
            iv_consideration=f"IV at {iv_percentile:.0f}th percentile",
            alternative_expiry=None,
            alternative_reason=None
        )
    
    def _get_theta_zone(self, days: int) -> str:
        """Classify theta severity."""
        if days > 14:
            return "GREEN"
        elif days > 7:
            return "YELLOW"
        elif days > 3:
            return "ORANGE"
        else:
            return "RED"
    
    def _get_weekly_expiry(self, current_date: date) -> date:
        """Get this week's or next week's Thursday expiry."""
        days_until_thursday = (self.weekly_expiry_day - current_date.weekday()) % 7
        
        # If it's Thursday or later, get next week's Thursday
        if days_until_thursday == 0 and datetime.now().hour >= 15:
            # After market close on Thursday, use next week
            days_until_thursday = 7
        elif days_until_thursday == 0:
            # Thursday before 3:30 PM, use today
            pass
        
        return current_date + timedelta(days=days_until_thursday)
    
    def _get_monthly_expiry(self, current_date: date) -> date:
        """Get last Thursday of current month (or next if passed)."""
        # Start with current month
        year = current_date.year
        month = current_date.month
        
        monthly = self._last_thursday_of_month(year, month)
        
        # If monthly expiry has passed, get next month's
        if monthly <= current_date:
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            monthly = self._last_thursday_of_month(year, month)
        
        return monthly
    
    def _last_thursday_of_month(self, year: int, month: int) -> date:
        """Get last Thursday of a month."""
        # Start from last day of month
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        
        last_day = next_month - timedelta(days=1)
        
        # Find last Thursday
        days_since_thursday = (last_day.weekday() - 3) % 7
        return last_day - timedelta(days=days_since_thursday)
    
    def get_all_expiries(
        self,
        current_date: Optional[date] = None,
        weeks_ahead: int = 4
    ) -> List[Dict]:
        """Get list of upcoming expiries."""
        if current_date is None:
            current_date = date.today()
        
        expiries = []
        
        # Weekly expiries
        weekly = self._get_weekly_expiry(current_date)
        for i in range(weeks_ahead):
            exp_date = weekly + timedelta(weeks=i)
            days_left = (exp_date - current_date).days
            
            expiries.append({
                "date": exp_date.isoformat(),
                "type": "WEEKLY",
                "days": days_left,
                "theta_zone": self._get_theta_zone(days_left),
                "viable_for_buying": days_left >= 2
            })
        
        # Monthly expiry
        monthly = self._get_monthly_expiry(current_date)
        days_left = (monthly - current_date).days
        
        expiries.append({
            "date": monthly.isoformat(),
            "type": "MONTHLY",
            "days": days_left,
            "theta_zone": self._get_theta_zone(days_left),
            "viable_for_buying": True
        })
        
        # Sort by date
        expiries.sort(key=lambda x: x["date"])
        
        return expiries
    
    def should_avoid_weekly(
        self,
        current_date: Optional[date] = None
    ) -> Tuple[bool, str]:
        """Quick check if weekly should be avoided."""
        if current_date is None:
            current_date = date.today()
        
        weekly = self._get_weekly_expiry(current_date)
        days_left = (weekly - current_date).days
        
        if days_left < 2:
            return True, f"Only {days_left} days to weekly expiry - high theta risk"
        
        if days_left == 2 and current_date.weekday() == 1:  # Tuesday
            return True, "2 days to expiry - consider monthly for swing trades"
        
        return False, f"Weekly viable with {days_left} days remaining"


# Singleton
expiry_evaluator = ExpiryEvaluator()

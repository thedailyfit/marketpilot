"""
Weekly Expiry Calendar
Manages Indian market weekly expiry schedules and expiry-day logic.
"""
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List, Dict
import logging


logger = logging.getLogger(__name__)


@dataclass
class ExpiryInfo:
    """Expiry information for an index."""
    symbol: str
    expiry_date: datetime
    days_to_expiry: int
    is_expiry_day: bool
    time_to_expiry_hours: float
    theta_acceleration: float  # Theta decay multiplier


class WeeklyExpiryCalendar:
    """
    Manages Indian market weekly expiry schedules.
    
    Weekly Expiry Schedule (2024):
    - Monday: Midcap Nifty (MIDCPNIFTY)
    - Tuesday: Finnifty (FINNIFTY)
    - Wednesday: Bank Nifty (BANKNIFTY)
    - Thursday: Nifty 50 (NIFTY)
    
    Monthly Expiry:
    - Last Thursday of month: All indices
    """
    
    # Weekly expiry day mapping (0=Monday, 6=Sunday)
    WEEKLY_EXPIRY_DAYS = {
        "MIDCPNIFTY": 0,   # Monday
        "FINNIFTY": 1,     # Tuesday
        "BANKNIFTY": 2,    # Wednesday
        "NIFTY": 3,        # Thursday
        "NIFTY 50": 3,     # Alias
        "NSE_INDEX|Nifty 50": 3  # Upstox format
    }
    
    # Trading hours (IST)
    MARKET_OPEN = 9.25   # 9:15 AM
    MARKET_CLOSE = 15.5  # 3:30 PM
    
    def __init__(self):
        self.holidays: List[datetime] = []
        self._load_holidays()
    
    def _load_holidays(self):
        """Load NSE trading holidays."""
        # 2024-2025 NSE holidays (major ones)
        holiday_dates = [
            "2024-01-26",  # Republic Day
            "2024-03-08",  # Maha Shivaratri
            "2024-03-25",  # Holi
            "2024-03-29",  # Good Friday
            "2024-04-14",  # Ambedkar Jayanti
            "2024-04-17",  # Ram Navami
            "2024-04-21",  # Mahavir Jayanti
            "2024-05-23",  # Buddha Purnima
            "2024-06-17",  # Eid
            "2024-07-17",  # Muharram
            "2024-08-15",  # Independence Day
            "2024-10-02",  # Gandhi Jayanti
            "2024-10-12",  # Dussehra
            "2024-11-01",  # Diwali Laxmi Puja
            "2024-11-15",  # Guru Nanak Jayanti
            "2024-12-25",  # Christmas
            # 2025 holidays
            "2025-01-26",  # Republic Day
            "2025-02-26",  # Maha Shivaratri
            "2025-03-14",  # Holi
            "2025-03-31",  # Eid
            "2025-04-10",  # Mahavir Jayanti
            "2025-04-14",  # Ambedkar Jayanti
            "2025-04-18",  # Good Friday
            "2025-05-12",  # Buddha Purnima
            "2025-08-15",  # Independence Day
            "2025-08-27",  # Janmashtami
            "2025-10-02",  # Gandhi Jayanti/Dussehra
            "2025-10-21",  # Diwali
            "2025-11-05",  # Guru Nanak Jayanti
            "2025-12-25",  # Christmas
        ]
        
        self.holidays = [datetime.strptime(d, "%Y-%m-%d").date() for d in holiday_dates]
    
    def is_trading_day(self, date: datetime = None) -> bool:
        """Check if given date is a trading day."""
        if date is None:
            date = datetime.now()
        
        # Weekend check
        if date.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Holiday check
        if date.date() in self.holidays:
            return False
        
        return True
    
    def get_expiry_day(self, symbol: str) -> int:
        """Get the weekday number for expiry."""
        symbol_upper = symbol.upper()
        return self.WEEKLY_EXPIRY_DAYS.get(symbol_upper, 3)  # Default Thursday
    
    def get_next_expiry(self, symbol: str, from_date: datetime = None) -> datetime:
        """
        Calculate next expiry date for a symbol.
        Handles holiday adjustments.
        """
        if from_date is None:
            from_date = datetime.now()
        
        expiry_day = self.get_expiry_day(symbol)
        
        # Calculate days until next expiry
        days_ahead = expiry_day - from_date.weekday()
        
        if days_ahead < 0:  # Expiry day already passed this week
            days_ahead += 7
        elif days_ahead == 0:
            # Same day - check if before 3:30 PM
            if from_date.hour >= 15 and from_date.minute >= 30:
                days_ahead = 7  # Next week
        
        next_expiry = from_date + timedelta(days=days_ahead)
        next_expiry = next_expiry.replace(hour=15, minute=30, second=0, microsecond=0)
        
        # Adjust for holidays
        while not self.is_trading_day(next_expiry):
            next_expiry -= timedelta(days=1)  # Move to previous trading day
        
        return next_expiry
    
    def get_expiry_info(self, symbol: str, from_date: datetime = None) -> ExpiryInfo:
        """Get complete expiry information for a symbol."""
        if from_date is None:
            from_date = datetime.now()
        
        next_expiry = self.get_next_expiry(symbol, from_date)
        
        # Calculate days to expiry
        delta = next_expiry.date() - from_date.date()
        days_to_expiry = delta.days
        
        # Is it expiry day?
        is_expiry_day = days_to_expiry == 0
        
        # Calculate hours to expiry
        time_delta = next_expiry - from_date
        time_to_expiry_hours = time_delta.total_seconds() / 3600
        
        # Theta acceleration factor
        # Theta decays faster as expiry approaches
        theta_acceleration = self._calculate_theta_acceleration(time_to_expiry_hours)
        
        return ExpiryInfo(
            symbol=symbol,
            expiry_date=next_expiry,
            days_to_expiry=days_to_expiry,
            is_expiry_day=is_expiry_day,
            time_to_expiry_hours=max(0, time_to_expiry_hours),
            theta_acceleration=theta_acceleration
        )
    
    def _calculate_theta_acceleration(self, hours_to_expiry: float) -> float:
        """
        Calculate theta decay acceleration.
        Theta accelerates as options approach expiry.
        
        Returns:
            Multiplier (1.0 = normal, higher = faster decay)
        """
        if hours_to_expiry <= 0:
            return 10.0  # Expired
        elif hours_to_expiry <= 2:  # Last 2 hours
            return 5.0
        elif hours_to_expiry <= 6:  # Last 6 hours
            return 3.0
        elif hours_to_expiry <= 24:  # Last day
            return 2.0
        elif hours_to_expiry <= 48:  # Last 2 days
            return 1.5
        else:
            return 1.0  # Normal decay
    
    def get_todays_expiry(self) -> Optional[str]:
        """Get which index expires today, if any."""
        today = datetime.now()
        
        if not self.is_trading_day(today):
            return None
        
        weekday = today.weekday()
        
        for symbol, expiry_day in self.WEEKLY_EXPIRY_DAYS.items():
            if expiry_day == weekday:
                return symbol
        
        return None
    
    def should_avoid_expiry_trade(self, symbol: str, trade_type: str = "BUY") -> bool:
        """
        Determine if trading should be avoided due to expiry conditions.
        
        - Avoid buying options on expiry day (theta decay too fast)
        - Consider selling on expiry day for premium collection
        """
        info = self.get_expiry_info(symbol)
        
        if info.is_expiry_day:
            if trade_type.upper() == "BUY":
                # Avoid buying on expiry - theta will kill premium
                if info.time_to_expiry_hours < 4:
                    return True
            # Selling is okay on expiry (we want premium decay)
        
        return False
    
    def get_expiry_strategy_recommendation(self, symbol: str) -> Dict:
        """Get strategy recommendations based on expiry timing."""
        info = self.get_expiry_info(symbol)
        
        if info.is_expiry_day:
            if info.time_to_expiry_hours < 2:
                return {
                    "strategy": "CLOSE_ALL",
                    "reason": "Last 2 hours of expiry. Close all positions.",
                    "theta_impact": "EXTREME"
                }
            elif info.time_to_expiry_hours < 4:
                return {
                    "strategy": "SELL_ONLY",
                    "reason": "Expiry day afternoon. Only sell options.",
                    "theta_impact": "HIGH"
                }
            else:
                return {
                    "strategy": "DIRECTIONAL_ONLY",
                    "reason": "Morning of expiry. Directional trades with tight SL.",
                    "theta_impact": "HIGH"
                }
        elif info.days_to_expiry == 1:
            return {
                "strategy": "THETA_HARVEST",
                "reason": "1 day to expiry. Good for option selling.",
                "theta_impact": "MEDIUM"
            }
        else:
            return {
                "strategy": "NORMAL",
                "reason": "Normal trading conditions.",
                "theta_impact": "LOW"
            }


# Global instance
expiry_calendar = WeeklyExpiryCalendar()

"""
Drawdown Guard
Hard enforcement of daily/weekly drawdown limits.
"""
import logging
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime, date


@dataclass
class DrawdownStatus:
    """Current drawdown status."""
    daily_pnl: float
    daily_limit: float
    daily_pct: float
    weekly_pnl: float
    weekly_limit: float
    weekly_pct: float
    is_paused: bool
    pause_reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_limit": round(self.daily_limit, 2),
            "daily_pct": round(self.daily_pct, 2),
            "weekly_pnl": round(self.weekly_pnl, 2),
            "weekly_limit": round(self.weekly_limit, 2),
            "weekly_pct": round(self.weekly_pct, 2),
            "is_paused": self.is_paused,
            "pause_reason": self.pause_reason
        }


class DrawdownGuard:
    """
    Hard enforcement of drawdown limits.
    
    Limits (of capital):
    - Daily max loss: -3% (warning at -2%)
    - Intraday pause: -5% (resume next day)
    - Weekly max: -10% (hard stop, manual reset required)
    
    This is a HARD GATE - no trade proceeds if limits are breached.
    """
    
    def __init__(self, capital: float = 500000):
        self.logger = logging.getLogger("DrawdownGuard")
        self.capital = capital
        
        # Limits as percentage of capital
        self.daily_warning_pct = 2.0      # -2% warning
        self.daily_limit_pct = 3.0        # -3% soft stop (reduce size)
        self.daily_pause_pct = 5.0        # -5% pause (no new trades)
        self.weekly_limit_pct = 10.0      # -10% hard stop
        
        # Tracking
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.is_paused = False
        self.pause_reason = None
        self.current_date = date.today()
        self.week_start = self._get_week_start()
        
    def _get_week_start(self) -> date:
        """Get Monday of current week."""
        today = date.today()
        return today.replace(day=today.day - today.weekday())
    
    def update_capital(self, capital: float):
        """Update capital for limit calculations."""
        self.capital = capital
        self.logger.info(f"Capital updated to ₹{capital:,.0f}")
    
    def record_pnl(self, pnl: float):
        """
        Record P&L from a closed trade.
        
        Args:
            pnl: Profit (positive) or loss (negative) in rupees
        """
        # Check for day/week rollover
        self._check_rollover()
        
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
        
        self.logger.debug(f"P&L recorded: ₹{pnl:.2f} | Daily: ₹{self.daily_pnl:.2f} | Weekly: ₹{self.weekly_pnl:.2f}")
        
        # Check if we've hit limits
        self._check_limits()
    
    def _check_rollover(self):
        """Check for day/week rollover."""
        today = date.today()
        week_start = self._get_week_start()
        
        # New day
        if today != self.current_date:
            self.daily_pnl = 0.0
            self.current_date = today
            
            # Clear daily pause (but not weekly)
            if self.pause_reason and "DAILY" in self.pause_reason:
                self.is_paused = False
                self.pause_reason = None
                self.logger.info("📅 New day - daily pause cleared")
        
        # New week
        if week_start != self.week_start:
            self.weekly_pnl = 0.0
            self.week_start = week_start
            
            # Clear all pauses
            self.is_paused = False
            self.pause_reason = None
            self.logger.info("📅 New week - all pauses cleared")
    
    def _check_limits(self):
        """Check if drawdown limits have been hit."""
        daily_pct = abs(self.daily_pnl) / self.capital * 100 if self.capital > 0 else 0
        weekly_pct = abs(self.weekly_pnl) / self.capital * 100 if self.capital > 0 else 0
        
        # Only check if we're in a loss
        if self.daily_pnl < 0:
            if daily_pct >= self.daily_pause_pct:
                self.is_paused = True
                self.pause_reason = f"DAILY_PAUSE: -{daily_pct:.1f}% hit {self.daily_pause_pct}% limit"
                self.logger.warning(f"🛑 TRADING PAUSED: {self.pause_reason}")
        
        if self.weekly_pnl < 0:
            if weekly_pct >= self.weekly_limit_pct:
                self.is_paused = True
                self.pause_reason = f"WEEKLY_STOP: -{weekly_pct:.1f}% hit {self.weekly_limit_pct}% limit"
                self.logger.error(f"🚨 HARD STOP: {self.pause_reason}")
    
    def check(self) -> Dict[str, any]:
        """
        Check if trading is allowed based on drawdown limits.
        
        Returns:
            Dict with allowed, reason, size_modifier
        """
        self._check_rollover()
        
        # If already paused
        if self.is_paused:
            return {
                "allowed": False,
                "reason": self.pause_reason,
                "size_modifier": 0.0
            }
        
        daily_pct = abs(self.daily_pnl) / self.capital * 100 if self.capital > 0 else 0
        weekly_pct = abs(self.weekly_pnl) / self.capital * 100 if self.capital > 0 else 0
        
        # Check weekly first (more severe)
        if self.weekly_pnl < 0 and weekly_pct >= self.weekly_limit_pct:
            return {
                "allowed": False,
                "reason": f"WEEKLY_STOP: -{weekly_pct:.1f}% exceeds {self.weekly_limit_pct}% limit",
                "size_modifier": 0.0
            }
        
        # Check daily pause
        if self.daily_pnl < 0 and daily_pct >= self.daily_pause_pct:
            return {
                "allowed": False,
                "reason": f"DAILY_PAUSE: -{daily_pct:.1f}% exceeds {self.daily_pause_pct}% limit",
                "size_modifier": 0.0
            }
        
        # Check daily limit (reduce size)
        if self.daily_pnl < 0 and daily_pct >= self.daily_limit_pct:
            return {
                "allowed": True,
                "warning": f"DAILY_LIMIT: -{daily_pct:.1f}% near limit, size reduced",
                "size_modifier": 0.5,  # 50% size
                "remaining_budget": round(self.capital * (self.daily_pause_pct / 100) - abs(self.daily_pnl), 2)
            }
        
        # Check daily warning
        if self.daily_pnl < 0 and daily_pct >= self.daily_warning_pct:
            return {
                "allowed": True,
                "warning": f"DAILY_WARNING: -{daily_pct:.1f}% approaching limit",
                "size_modifier": 0.75,  # 75% size
                "remaining_budget": round(self.capital * (self.daily_limit_pct / 100) - abs(self.daily_pnl), 2)
            }
        
        # All clear
        return {
            "allowed": True,
            "size_modifier": 1.0,
            "daily_pnl": round(self.daily_pnl, 2),
            "weekly_pnl": round(self.weekly_pnl, 2)
        }
    
    def get_status(self) -> DrawdownStatus:
        """Get current drawdown status."""
        daily_pct = abs(self.daily_pnl) / self.capital * 100 if self.capital > 0 else 0
        weekly_pct = abs(self.weekly_pnl) / self.capital * 100 if self.capital > 0 else 0
        
        return DrawdownStatus(
            daily_pnl=self.daily_pnl,
            daily_limit=self.capital * self.daily_pause_pct / 100,
            daily_pct=daily_pct if self.daily_pnl < 0 else 0,
            weekly_pnl=self.weekly_pnl,
            weekly_limit=self.capital * self.weekly_limit_pct / 100,
            weekly_pct=weekly_pct if self.weekly_pnl < 0 else 0,
            is_paused=self.is_paused,
            pause_reason=self.pause_reason
        )
    
    def manual_reset(self, reason: str = "Manual reset"):
        """
        Manually reset drawdown guard.
        Use with caution - bypasses safety limits.
        """
        self.logger.warning(f"⚠️ MANUAL RESET: {reason}")
        self.daily_pnl = 0.0
        self.is_paused = False
        self.pause_reason = None
        # Note: Weekly is NOT reset - that requires week rollover
    
    def force_weekly_reset(self, reason: str = "Forced weekly reset"):
        """
        Force reset weekly limits.
        DANGEROUS - use only in emergencies.
        """
        self.logger.error(f"🚨 FORCED WEEKLY RESET: {reason}")
        self.weekly_pnl = 0.0
        self.is_paused = False
        self.pause_reason = None


# Singleton
drawdown_guard = DrawdownGuard()

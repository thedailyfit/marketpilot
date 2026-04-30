"""
Trade Frequency Regulator
Prevents over-trading by limiting daily trades.
"""
import logging
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime, date
from pathlib import Path


@dataclass
class TradeEntry:
    """Single trade record."""
    trade_id: str
    timestamp: int
    symbol: str
    side: str  # BUY, SELL


@dataclass
class FrequencyStatus:
    """Current frequency status."""
    trades_today: int
    max_daily: int
    remaining: int
    
    over_trading: bool
    warning: Optional[str]
    recommendation: str
    
    # Time-based
    last_trade_mins_ago: int
    cooldown_active: bool
    
    def to_dict(self) -> dict:
        return {
            "trades_today": self.trades_today,
            "max_daily": self.max_daily,
            "remaining": self.remaining,
            "over_trading": self.over_trading,
            "warning": self.warning,
            "recommendation": self.recommendation,
            "last_trade_mins_ago": self.last_trade_mins_ago
        }


class TradeFrequencyRegulator:
    """
    Prevents over-trading by limiting trade frequency.
    
    Rules:
    - Max N trades per day (default: 3)
    - Minimum cooldown between trades
    - Warning at 2/3 capacity
    - Hard block at limit
    
    Psychology:
    - Forces selectivity
    - Prevents revenge trading
    - Allows reflection between trades
    """
    
    def __init__(self, max_daily: int = 3, cooldown_minutes: int = 15):
        self.logger = logging.getLogger("FrequencyRegulator")
        
        self.max_daily = max_daily
        self.cooldown_minutes = cooldown_minutes
        
        # Today's trades
        self.trades_today: List[TradeEntry] = []
        self.last_trade_time: Optional[int] = None
        
        # Historical
        self.daily_history: Dict[str, int] = {}
        
        # Persistence
        self.data_path = Path("data/governor/frequency.json")
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._load()
    
    def set_max_daily(self, max_trades: int):
        """Update daily limit."""
        self.max_daily = max_trades
        self.logger.info(f"Daily trade limit set to {max_trades}")
    
    def record_trade(self, trade_id: str, symbol: str, side: str):
        """Record a new trade."""
        entry = TradeEntry(
            trade_id=trade_id,
            timestamp=int(datetime.now().timestamp()),
            symbol=symbol,
            side=side
        )
        
        self.trades_today.append(entry)
        self.last_trade_time = entry.timestamp
        
        self._save()
        
        self.logger.info(
            f"Trade recorded: {trade_id} | Today: {len(self.trades_today)}/{self.max_daily}"
        )
    
    def check(self, context: Optional[Dict] = None) -> FrequencyStatus:
        """
        Check current frequency status.
        
        Returns:
            FrequencyStatus with limits and recommendations
        """
        trades = len(self.trades_today)
        remaining = max(0, self.max_daily - trades)
        
        # Check over-trading
        over_trading = trades >= self.max_daily
        
        # Check cooldown
        cooldown_active = False
        last_trade_mins = 999
        
        if self.last_trade_time:
            mins_since = (int(datetime.now().timestamp()) - self.last_trade_time) // 60
            last_trade_mins = mins_since
            
            if mins_since < self.cooldown_minutes:
                cooldown_active = True
        
        # Generate warning
        warning = None
        if over_trading:
            warning = f"Daily limit reached: {trades}/{self.max_daily} trades"
        elif trades >= self.max_daily * 0.66:
            warning = f"Nearing limit: {trades}/{self.max_daily} trades used"
        elif cooldown_active:
            wait = self.cooldown_minutes - last_trade_mins
            warning = f"Cooldown active: wait {wait} more minutes"
        
        # Generate recommendation
        if over_trading:
            recommendation = "STOP - daily limit reached, wait until tomorrow"
        elif cooldown_active:
            recommendation = "WAIT - cooldown period active"
        elif remaining == 1:
            recommendation = "LAST TRADE - high conviction only"
        elif remaining == 2:
            recommendation = "2 trades remaining - be selective"
        else:
            recommendation = "Normal trading"
        
        return FrequencyStatus(
            trades_today=trades,
            max_daily=self.max_daily,
            remaining=remaining,
            over_trading=over_trading,
            warning=warning,
            recommendation=recommendation,
            last_trade_mins_ago=last_trade_mins,
            cooldown_active=cooldown_active
        )
    
    def can_trade(self) -> tuple:
        """Quick check if trading is allowed."""
        status = self.check()
        
        if status.over_trading:
            return False, "Daily trade limit reached"
        
        if status.cooldown_active:
            return False, f"Cooldown active ({self.cooldown_minutes - status.last_trade_mins_ago} mins remaining)"
        
        return True, f"{status.remaining} trades remaining today"
    
    def reset_daily(self):
        """Reset for new trading day."""
        today = date.today().isoformat()
        self.daily_history[today] = len(self.trades_today)
        
        self.trades_today = []
        self.last_trade_time = None
        
        self._save()
        self.logger.info("Daily trade counter reset")
    
    def get_historical_average(self, days: int = 7) -> float:
        """Get average daily trades over last N days."""
        if not self.daily_history:
            return 0
        
        values = list(self.daily_history.values())[-days:]
        return sum(values) / len(values) if values else 0
    
    def _save(self):
        """Save state to disk."""
        data = {
            "max_daily": self.max_daily,
            "cooldown_minutes": self.cooldown_minutes,
            "trades_today": [asdict(t) for t in self.trades_today],
            "last_trade_time": self.last_trade_time,
            "daily_history": self.daily_history,
            "date": date.today().isoformat()
        }
        
        with open(self.data_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load(self):
        """Load state from disk."""
        if not self.data_path.exists():
            return
        
        try:
            with open(self.data_path) as f:
                data = json.load(f)
            
            # Check if same day
            if data.get("date") == date.today().isoformat():
                self.trades_today = [TradeEntry(**t) for t in data.get("trades_today", [])]
                self.last_trade_time = data.get("last_trade_time")
            
            self.daily_history = data.get("daily_history", {})
            
        except Exception as e:
            self.logger.warning(f"Failed to load frequency data: {e}")


# Singleton
frequency_regulator = TradeFrequencyRegulator()

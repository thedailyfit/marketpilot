"""
Performance Tracker
Tracks and calculates trading performance metrics.
"""
import json
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


DATA_FILE = "data/performance_history.json"


@dataclass
class DailyStats:
    date: str
    starting_balance: float
    ending_balance: float
    pnl: float
    trades: int
    wins: int
    losses: int
    max_drawdown: float
    win_rate: float


class PerformanceTracker:
    """Tracks and calculates trading performance metrics."""
    
    def __init__(self):
        self.trade_history: List[dict] = []
        self.equity_curve: List[dict] = []  # [{timestamp, balance, pnl}]
        self.daily_stats: List[DailyStats] = []
        self.starting_balance: float = 100000.0
        self.current_balance: float = 100000.0
        self.peak_balance: float = 100000.0
        self.max_drawdown: float = 0.0
        self.max_drawdown_percent: float = 0.0
        
        self._load_data()
    
    def _load_data(self):
        """Load historical data from file."""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
                    self.trade_history = data.get('trades', [])
                    self.equity_curve = data.get('equity', [])
                    self.current_balance = data.get('balance', 100000.0)
                    self.peak_balance = data.get('peak', 100000.0)
            except Exception:
                pass
    
    def _save_data(self):
        """Save data to file."""
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump({
                'trades': self.trade_history[-1000:],  # Keep last 1000
                'equity': self.equity_curve[-500:],    # Keep last 500
                'balance': self.current_balance,
                'peak': self.peak_balance
            }, f)
    
    def record_trade(self, trade: dict):
        """Record a completed trade."""
        pnl = trade.get('pnl', 0.0)
        
        self.trade_history.append({
            'timestamp': trade.get('timestamp', datetime.now().isoformat()),
            'symbol': trade.get('symbol', 'UNKNOWN'),
            'direction': trade.get('action', 'BUY'),
            'quantity': trade.get('quantity', 0),
            'entry_price': trade.get('entry_price', 0),
            'exit_price': trade.get('fill_price', 0),
            'pnl': pnl,
            'strategy': trade.get('strategy_id', 'UNKNOWN')
        })
        
        # Update balance
        self.current_balance += pnl
        
        # Update peak and drawdown
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        drawdown = self.peak_balance - self.current_balance
        drawdown_percent = (drawdown / self.peak_balance) * 100 if self.peak_balance > 0 else 0
        
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
            self.max_drawdown_percent = drawdown_percent
        
        # Add to equity curve
        self.equity_curve.append({
            'timestamp': datetime.now().timestamp(),
            'balance': self.current_balance,
            'pnl': pnl,
            'drawdown': drawdown_percent
        })
        
        self._save_data()
    
    def get_equity_curve(self, limit: int = 100) -> List[dict]:
        """Get equity curve data for charting."""
        return self.equity_curve[-limit:]
    
    def get_drawdown_history(self, limit: int = 100) -> List[dict]:
        """Get drawdown history for charting."""
        return [
            {'timestamp': e['timestamp'], 'drawdown': e.get('drawdown', 0)}
            for e in self.equity_curve[-limit:]
        ]
    
    def get_trade_distribution(self) -> dict:
        """Get trade distribution by hour and day."""
        by_hour = {str(h): {'count': 0, 'pnl': 0, 'wins': 0} for h in range(9, 16)}
        by_day = {str(d): {'count': 0, 'pnl': 0, 'wins': 0} for d in range(5)}
        by_strategy = {}
        
        for trade in self.trade_history:
            try:
                ts = trade.get('timestamp', '')
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts)
                else:
                    dt = datetime.fromtimestamp(ts)
                
                hour = str(dt.hour)
                day = str(dt.weekday())
                pnl = trade.get('pnl', 0)
                strategy = trade.get('strategy', 'UNKNOWN')
                
                # By hour
                if hour in by_hour:
                    by_hour[hour]['count'] += 1
                    by_hour[hour]['pnl'] += pnl
                    if pnl > 0:
                        by_hour[hour]['wins'] += 1
                
                # By day
                if day in by_day:
                    by_day[day]['count'] += 1
                    by_day[day]['pnl'] += pnl
                    if pnl > 0:
                        by_day[day]['wins'] += 1
                
                # By strategy
                if strategy not in by_strategy:
                    by_strategy[strategy] = {'count': 0, 'pnl': 0, 'wins': 0}
                by_strategy[strategy]['count'] += 1
                by_strategy[strategy]['pnl'] += pnl
                if pnl > 0:
                    by_strategy[strategy]['wins'] += 1
                    
            except Exception:
                continue
        
        return {
            'by_hour': by_hour,
            'by_day': by_day,
            'by_strategy': by_strategy
        }
    
    def get_performance_metrics(self) -> dict:
        """Calculate performance metrics."""
        if not self.trade_history:
            return self._default_metrics()
        
        trades = self.trade_history
        pnls = [t.get('pnl', 0) for t in trades]
        
        total_pnl = sum(pnls)
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        win_rate = len(wins) / len(pnls) * 100 if pnls else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Sharpe Ratio (simplified - assumes daily returns)
        if len(pnls) > 1:
            import statistics
            mean_return = statistics.mean(pnls)
            std_return = statistics.stdev(pnls) if len(pnls) > 1 else 1
            sharpe = (mean_return / std_return) * (252 ** 0.5) if std_return > 0 else 0
        else:
            sharpe = 0
        
        # Win/Loss streaks
        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        temp_streak = 0
        last_was_win = None
        
        for pnl in pnls:
            is_win = pnl > 0
            if last_was_win is None:
                temp_streak = 1
            elif is_win == last_was_win:
                temp_streak += 1
            else:
                if last_was_win:
                    max_win_streak = max(max_win_streak, temp_streak)
                else:
                    max_loss_streak = max(max_loss_streak, temp_streak)
                temp_streak = 1
            last_was_win = is_win
        
        # Final streak
        if last_was_win:
            max_win_streak = max(max_win_streak, temp_streak)
            current_streak = temp_streak
        else:
            max_loss_streak = max(max_loss_streak, temp_streak)
            current_streak = -temp_streak
        
        return {
            'total_trades': len(trades),
            'total_pnl': round(total_pnl, 2),
            'current_balance': round(self.current_balance, 2),
            'win_rate': round(win_rate, 1),
            'wins': len(wins),
            'losses': len(losses),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown': round(self.max_drawdown, 2),
            'max_drawdown_percent': round(self.max_drawdown_percent, 2),
            'current_streak': current_streak,
            'max_win_streak': max_win_streak,
            'max_loss_streak': max_loss_streak
        }
    
    def _default_metrics(self) -> dict:
        """Return default metrics when no trades."""
        return {
            'total_trades': 0,
            'total_pnl': 0.0,
            'current_balance': self.current_balance,
            'win_rate': 0.0,
            'wins': 0,
            'losses': 0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_percent': 0.0,
            'current_streak': 0,
            'max_win_streak': 0,
            'max_loss_streak': 0
        }
    
    def reset(self, starting_balance: float = 100000.0):
        """Reset tracker for new period."""
        self.trade_history = []
        self.equity_curve = []
        self.starting_balance = starting_balance
        self.current_balance = starting_balance
        self.peak_balance = starting_balance
        self.max_drawdown = 0.0
        self.max_drawdown_percent = 0.0
        self._save_data()


# Global instance
tracker = PerformanceTracker()

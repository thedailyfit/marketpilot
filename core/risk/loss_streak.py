"""
Options Loss Streak Dampener
Reduces position size after consecutive losses.
"""
import logging
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime, date
from pathlib import Path


@dataclass
class TradeResult:
    """Single trade result."""
    trade_id: str
    timestamp: int
    symbol: str
    pnl: float
    is_win: bool


@dataclass
class DampenerStatus:
    """Current dampener status."""
    consecutive_losses: int
    size_multiplier: float  # 1.0 = full size, 0.25 = quarter size
    
    # Historical
    recent_trades: int
    recent_wins: int
    recent_losses: int
    win_rate: float
    
    # Recommendation
    recommendation: str
    mode: str  # NORMAL, CAUTION, DEFENSIVE, RECOVERY
    
    def to_dict(self) -> dict:
        return {
            "streak": self.consecutive_losses,
            "size_multiplier": self.size_multiplier,
            "recent_trades": self.recent_trades,
            "win_rate": round(self.win_rate * 100, 1),
            "recommendation": self.recommendation,
            "mode": self.mode
        }


class OptionsLossStreakDampener:
    """
    Reduces position size after consecutive losses.
    
    Psychology:
    - Losses often cluster due to regime mismatch
    - Reducing size preserves capital for recovery
    - Forces reflection on strategy
    
    Rules:
    - 2 consecutive losses: 75% size
    - 3 consecutive losses: 50% size
    - 5+ consecutive losses: 25% size
    - After win: gradually restore size
    
    Recovery:
    - 1 win after streak: +20% size (max 1.0)
    - 2 consecutive wins: +30% size
    - 3 consecutive wins: full size restored
    """
    
    def __init__(self, data_path: Optional[str] = None):
        self.logger = logging.getLogger("LossStreakDampener")
        
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.size_multiplier = 1.0
        
        # Recent trade history
        self.trades: List[TradeResult] = []
        self.max_history = 50
        
        # Data persistence
        if data_path:
            self.data_path = Path(data_path)
        else:
            self.data_path = Path("data/governor/loss_streak.json")
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._load()
    
    def record_result(self, trade_id: str, symbol: str, pnl: float):
        """
        Record trade result and adjust size multiplier.
        
        Args:
            trade_id: Unique trade identifier
            symbol: Traded symbol
            pnl: Profit/loss in rupees
        """
        is_win = pnl > 0
        
        result = TradeResult(
            trade_id=trade_id,
            timestamp=int(datetime.now().timestamp()),
            symbol=symbol,
            pnl=pnl,
            is_win=is_win
        )
        
        self.trades.append(result)
        if len(self.trades) > self.max_history:
            self.trades = self.trades[-self.max_history:]
        
        if is_win:
            self._handle_win()
        else:
            self._handle_loss()
        
        self._save()
        
        self.logger.info(
            f"Trade recorded: {'WIN' if is_win else 'LOSS'} ₹{pnl:.0f} | "
            f"Streak: {self.consecutive_losses}L/{self.consecutive_wins}W | "
            f"Size: {self.size_multiplier*100:.0f}%"
        )
    
    def _handle_loss(self):
        """Handle a losing trade."""
        self.consecutive_losses += 1
        self.consecutive_wins = 0
        
        # Apply dampening
        if self.consecutive_losses >= 5:
            self.size_multiplier = 0.25
        elif self.consecutive_losses >= 3:
            self.size_multiplier = 0.50
        elif self.consecutive_losses >= 2:
            self.size_multiplier = 0.75
        # First loss doesn't dampen
    
    def _handle_win(self):
        """Handle a winning trade."""
        self.consecutive_wins += 1
        
        if self.consecutive_losses > 0:
            # Recovery mode
            if self.consecutive_wins >= 3:
                self.size_multiplier = 1.0
                self.consecutive_losses = 0
            elif self.consecutive_wins >= 2:
                self.size_multiplier = min(1.0, self.size_multiplier + 0.30)
            else:
                self.size_multiplier = min(1.0, self.size_multiplier + 0.20)
        else:
            # Normal operation
            self.consecutive_losses = 0
            self.size_multiplier = 1.0
    
    def get_adjusted_quantity(self, base_quantity: int) -> int:
        """
        Get size-adjusted quantity.
        
        Args:
            base_quantity: Desired quantity before adjustment
        
        Returns:
            Adjusted quantity based on loss streak
        """
        adjusted = int(base_quantity * self.size_multiplier)
        return max(1, adjusted)  # At least 1 lot
    
    def get_status(self) -> DampenerStatus:
        """Get current dampener status."""
        recent_trades = len(self.trades)
        recent_wins = sum(1 for t in self.trades if t.is_win)
        recent_losses = recent_trades - recent_wins
        win_rate = recent_wins / recent_trades if recent_trades > 0 else 0.5
        
        # Determine mode
        if self.consecutive_losses >= 5:
            mode = "DEFENSIVE"
            recommendation = "Strongly consider pausing trading"
        elif self.consecutive_losses >= 3:
            mode = "CAUTION"
            recommendation = "Reduce risk, high conviction only"
        elif self.consecutive_losses >= 2:
            mode = "RECOVERY"
            recommendation = "Trading with reduced size"
        else:
            mode = "NORMAL"
            recommendation = "Full position sizing"
        
        return DampenerStatus(
            consecutive_losses=self.consecutive_losses,
            size_multiplier=self.size_multiplier,
            recent_trades=recent_trades,
            recent_wins=recent_wins,
            recent_losses=recent_losses,
            win_rate=win_rate,
            recommendation=recommendation,
            mode=mode
        )
    
    def should_pause_trading(self) -> tuple:
        """Check if trading should be paused."""
        if self.consecutive_losses >= 7:
            return True, "7+ consecutive losses - mandatory pause recommended"
        
        if self.consecutive_losses >= 5:
            return False, "5+ losses - consider pausing, trading at 25% size"
        
        # Check recent win rate
        recent = self.trades[-10:] if len(self.trades) >= 10 else self.trades
        if recent:
            win_rate = sum(1 for t in recent if t.is_win) / len(recent)
            if win_rate < 0.2:  # Less than 20% win rate
                return True, f"Very low win rate ({win_rate*100:.0f}%) - review strategy"
        
        return False, "Trading allowed"
    
    def reset(self):
        """Reset dampener (e.g., new trading day)."""
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.size_multiplier = 1.0
        self.logger.info("Loss streak dampener reset")
    
    def _save(self):
        """Save state to disk."""
        data = {
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "size_multiplier": self.size_multiplier,
            "trades": [asdict(t) for t in self.trades[-20:]]  # Keep last 20
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
            
            self.consecutive_losses = data.get("consecutive_losses", 0)
            self.consecutive_wins = data.get("consecutive_wins", 0)
            self.size_multiplier = data.get("size_multiplier", 1.0)
            
            for t in data.get("trades", []):
                self.trades.append(TradeResult(**t))
                
        except Exception as e:
            self.logger.warning(f"Failed to load loss streak data: {e}")


# Singleton
loss_streak_dampener = OptionsLossStreakDampener()

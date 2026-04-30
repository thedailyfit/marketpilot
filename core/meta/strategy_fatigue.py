"""
StrategyFatigue - Edge Decay Detection & Auto-Cooldown
Detects strategy performance degradation and triggers protective measures.
"""
import json
import logging
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from core.event_bus import bus, EventType


@dataclass
class Trade:
    """Simplified trade record for fatigue analysis."""
    trade_id: str
    strategy: str
    direction: str
    pnl: float
    regime: str
    hour: int
    timestamp: int


@dataclass
class FatigueReport:
    """Fatigue analysis result for a strategy."""
    strategy: str
    fatigue_score: int  # 0-100
    action: str  # ACTIVE, COOLDOWN, DISABLE
    win_rate_current: float
    win_rate_baseline: float
    loss_streak: int
    z_score: float
    cooldown_until: Optional[int] = None
    metrics: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)


COOLDOWN_RULES = {
    "COOLDOWN": {"duration_minutes": 60, "max_trades": 1},
    "DISABLE": {"duration_minutes": 240, "max_trades": 0}
}


class StrategyFatigue:
    """
    Detects strategy edge decay using statistical methods.
    Triggers automatic cooldowns when performance degrades.
    """
    def __init__(self):
        self.logger = logging.getLogger("StrategyFatigue")
        self.trades: Dict[str, List[Trade]] = {}  # {strategy: [trades]}
        self.reports: Dict[str, FatigueReport] = {}
        self.cooldowns: Dict[str, int] = {}  # {strategy: cooldown_until_ts}
        self.db_path = Path("data/strategy_stats.json")
        self.is_running = False
        self._load()
        
    def _load(self):
        """Load existing trade history."""
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    for strategy, trade_list in data.get('trades', {}).items():
                        self.trades[strategy] = [Trade(**t) for t in trade_list]
                    self.cooldowns = data.get('cooldowns', {})
                self.logger.debug(f"Loaded {sum(len(t) for t in self.trades.values())} trades")
        except Exception as e:
            self.logger.error(f"Failed to load strategy stats: {e}")
            
    def _persist(self):
        """Save to disk."""
        try:
            self.db_path.parent.mkdir(exist_ok=True)
            data = {
                'trades': {s: [asdict(t) for t in trades] for s, trades in self.trades.items()},
                'cooldowns': self.cooldowns
            }
            with open(self.db_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to persist strategy stats: {e}")
            
    async def on_start(self):
        self.logger.info("Starting Strategy Fatigue Engine...")
        self.is_running = True
        # Re-analyze all strategies on startup
        for strategy in self.trades.keys():
            await self.analyze(strategy)
        
    async def on_stop(self):
        self.is_running = False
        self._persist()
        self.logger.info("Strategy Fatigue Engine Stopped")
        
    def record_trade(
        self,
        trade_id: str,
        strategy: str,
        direction: str,
        pnl: float,
        regime: str
    ):
        """Record a completed trade for fatigue analysis."""
        trade = Trade(
            trade_id=trade_id,
            strategy=strategy,
            direction=direction,
            pnl=pnl,
            regime=regime,
            hour=datetime.now().hour,
            timestamp=int(datetime.now().timestamp())
        )
        
        if strategy not in self.trades:
            self.trades[strategy] = []
        self.trades[strategy].append(trade)
        
        # Keep last 200 trades per strategy
        if len(self.trades[strategy]) > 200:
            self.trades[strategy] = self.trades[strategy][-200:]
        
        self._persist()
        
    async def analyze(self, strategy: str) -> Optional[FatigueReport]:
        """
        Analyze a strategy for fatigue using:
        - Win rate decay (current vs baseline)
        - Loss streak detection
        - Z-test for statistical significance
        """
        trades = self.trades.get(strategy, [])
        
        if len(trades) < 25:
            return None  # Not enough data
        
        recent = trades[-20:]  # Last 20 trades
        baseline = trades[-100:-20] if len(trades) > 30 else trades[:-20]
        
        if len(baseline) < 10:
            return None
        
        # 1. Win Rate Calculation
        current_wins = sum(1 for t in recent if t.pnl > 0)
        current_wr = current_wins / len(recent)
        
        baseline_wins = sum(1 for t in baseline if t.pnl > 0)
        baseline_wr = baseline_wins / len(baseline)
        
        wr_decay = baseline_wr - current_wr
        
        # 2. Loss Streak Count
        loss_streak = 0
        for t in reversed(recent):
            if t.pnl < 0:
                loss_streak += 1
            else:
                break
        
        # 3. Z-Test for significance
        # H0: current performance = baseline performance
        n = len(recent)
        if baseline_wr > 0:
            baseline_std = math.sqrt(baseline_wr * (1 - baseline_wr))
            if baseline_std > 0:
                z_score = (current_wr - baseline_wr) / (baseline_std / math.sqrt(n))
            else:
                z_score = 0
        else:
            z_score = 0
        
        is_significant = abs(z_score) > 1.96  # 95% confidence
        
        # 4. Calculate Fatigue Score
        fatigue_score = 0
        
        if wr_decay > 0.15:
            fatigue_score += 40
        elif wr_decay > 0.10:
            fatigue_score += 25
        elif wr_decay > 0.05:
            fatigue_score += 10
        
        if loss_streak >= 7:
            fatigue_score += 40
        elif loss_streak >= 5:
            fatigue_score += 30
        elif loss_streak >= 3:
            fatigue_score += 15
        
        if is_significant and z_score < -1.96:
            fatigue_score += 30
        elif is_significant and z_score < -1.5:
            fatigue_score += 15
        
        fatigue_score = min(100, fatigue_score)
        
        # 5. Determine Action
        if fatigue_score >= 70:
            action = "DISABLE"
            duration = COOLDOWN_RULES["DISABLE"]["duration_minutes"]
            self.cooldowns[strategy] = int(datetime.now().timestamp()) + (duration * 60)
        elif fatigue_score >= 40:
            action = "COOLDOWN"
            duration = COOLDOWN_RULES["COOLDOWN"]["duration_minutes"]
            self.cooldowns[strategy] = int(datetime.now().timestamp()) + (duration * 60)
        else:
            action = "ACTIVE"
            if strategy in self.cooldowns:
                del self.cooldowns[strategy]
        
        # Create report
        report = FatigueReport(
            strategy=strategy,
            fatigue_score=fatigue_score,
            action=action,
            win_rate_current=current_wr,
            win_rate_baseline=baseline_wr,
            loss_streak=loss_streak,
            z_score=z_score,
            cooldown_until=self.cooldowns.get(strategy),
            metrics={
                "trades_analyzed": len(recent),
                "baseline_trades": len(baseline),
                "wr_decay": round(wr_decay, 3),
                "is_significant": is_significant
            }
        )
        
        self.reports[strategy] = report
        self._persist()
        
        # Log and emit
        if action != "ACTIVE":
            self.logger.warning(f"⚠️ STRATEGY FATIGUE: {strategy} -> {action} (score: {fatigue_score})")
            await bus.publish(EventType.STRATEGY_FATIGUE, report.to_dict())
        
        return report
    
    def is_allowed(self, strategy: str) -> tuple:
        """Check if strategy is allowed to trade."""
        now = int(datetime.now().timestamp())
        
        if strategy in self.cooldowns:
            cooldown_until = self.cooldowns[strategy]
            if now < cooldown_until:
                remaining = (cooldown_until - now) // 60
                return False, f"Cooldown: {remaining} min remaining"
            else:
                del self.cooldowns[strategy]
        
        return True, "Active"
    
    def get_regime_affinity(self, strategy: str) -> Dict[str, float]:
        """Calculate win rate by regime for a strategy."""
        trades = self.trades.get(strategy, [])
        
        regime_stats = {}
        for t in trades:
            if t.regime not in regime_stats:
                regime_stats[t.regime] = {'wins': 0, 'total': 0}
            regime_stats[t.regime]['total'] += 1
            if t.pnl > 0:
                regime_stats[t.regime]['wins'] += 1
        
        return {
            regime: stats['wins'] / stats['total'] if stats['total'] > 0 else 0
            for regime, stats in regime_stats.items()
        }
    
    def get_report(self, strategy: str) -> Optional[dict]:
        """Get latest fatigue report."""
        report = self.reports.get(strategy)
        return report.to_dict() if report else None


# Singleton
strategy_fatigue = StrategyFatigue()

"""
Performance Tracker
Tracks metrics specifically tied to strategy VERSIONS.
"""
import logging
from collections import defaultdict, deque
from typing import Dict, List

class VersionMetrics:
    def __init__(self):
        self.trades = 0
        self.wins = 0
        self.total_pnl = 0.0
        self.pnl_history = deque(maxlen=20) # For rolling win rate
        self.drawdown = 0.0
        self.peak_equity = 0.0
        self.current_equity = 0.0 # Tracks PnL accumulation
        
    def update(self, pnl: float):
        self.trades += 1
        self.total_pnl += pnl
        self.current_equity += pnl
        
        if pnl > 0:
            self.wins += 1
            self.pnl_history.append(1)
        else:
            self.pnl_history.append(0)
            
        # Drawdown Calc
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity
            self.drawdown = 0.0
        else:
            # Simple absolute drawdown from peak PnL
            dd = self.peak_equity - self.current_equity
            self.drawdown = dd 

    @property
    def win_rate(self) -> float:
        if not self.pnl_history:
            return 0.0
        return (sum(self.pnl_history) / len(self.pnl_history)) * 100

class PerformanceTracker:
    """
    Tracks performance per (Strategy, Version).
    """
    def __init__(self):
        self.logger = logging.getLogger("PerfTracker")
        # Key: "StrategyName:VersionID" -> VersionMetrics
        self.metrics: Dict[str, VersionMetrics] = defaultdict(VersionMetrics)
        
    def record_trade(self, strategy: str, version: str, pnl: float):
        """Update metrics for a specific version."""
        key = f"{strategy}:{version}"
        self.metrics[key].update(pnl)
        
        m = self.metrics[key]
        self.logger.info(f"📈 Stats {key}: WinRate={m.win_rate:.1f}% DD={m.drawdown:.2f}")
        
    def get_metrics(self, strategy: str, version: str) -> VersionMetrics:
        return self.metrics[f"{strategy}:{version}"]

# Singleton
performance_tracker = PerformanceTracker()

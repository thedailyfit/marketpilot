"""
Rollback Engine
Detects strategy regression and triggers rollback.
"""
import logging
from typing import Dict, Optional
from .registry import strategy_registry
from .performance_tracker import performance_tracker

class RollbackEngine:
    """
    The Limit Switch for strategy logic.
    """
    def __init__(self):
        self.logger = logging.getLogger("RollbackEngine")
        
        # Thresholds
        self.MIN_TRADES_FOR_CHECK = 5
        self.WIN_RATE_DROP_THRESHOLD = 15.0 # If 15% worse than previous
        self.MAX_DRAWDOWN_THRESHOLD = 5000.0 # Absolute unit limit (e.g. $5000)
        
    def check_for_regression(self, strategy_name: str, current_version: str):
        """
        Compare current version against safety limits or previous version.
        """
        current_metrics = performance_tracker.get_metrics(strategy_name, current_version)
        
        if current_metrics.trades < self.MIN_TRADES_FOR_CHECK:
            return # Too early
            
        messages = []
        should_rollback = False
        
        # 1. Absolute Drawdown Check
        if current_metrics.drawdown > self.MAX_DRAWDOWN_THRESHOLD:
            should_rollback = True
            messages.append(f"Max Drawdown Breached ({current_metrics.drawdown} > {self.MAX_DRAWDOWN_THRESHOLD})")
            
        # 2. Variable Win Rate check against previous?
        # Requires looking up previous version stats.
        # For simplicity, let's just assert Min Win Rate for now.
        if current_metrics.win_rate < 30.0: # Very bad
            should_rollback = True
            messages.append(f"Win Rate Critical ({current_metrics.win_rate:.1f}%)")
            
        if should_rollback:
            reason = " & ".join(messages)
            self.logger.critical(f"🚫 REGRESSION DETECTED on {strategy_name} {current_version}: {reason}")
            
            # Execute Rollback
            new_version = strategy_registry.rollback_version(strategy_name)
            
            if new_version:
                self.logger.info(f"✅ Auto-Rolled back to {new_version}")
            else:
                self.logger.critical("❌ Rollback Failed - No stable parent!")

# Singleton
rollback_engine = RollbackEngine()

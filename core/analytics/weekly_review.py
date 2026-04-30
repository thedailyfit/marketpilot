"""
Weekly Review Engine
Aggregates trade data to find patterns and leaks.
"""
import logging
from typing import List, Dict
from collections import defaultdict
from .trade_journal import trade_journal, JournalEntry

class WeeklyReview:
    """
    Generates summary reports from the Trade Journal.
    Answers: "Where am I making/losing money?"
    """
    
    def __init__(self):
        self.logger = logging.getLogger("WeeklyReview")
        
    def generate_report(self) -> Dict:
        """
        Analyze all trades and generate stats.
        """
        trades = trade_journal.get_all_trades()
        if not trades:
            return {"status": "No Trades"}
            
        total_pnl = 0.0
        wins = 0
        losses = 0
        
        strategy_pnl = defaultdict(float)
        regime_pnl = defaultdict(float)
        best_trade = None
        worst_trade = None
        
        for t in trades:
            if t.exit_time == 0: continue # Skip open trades
            
            total_pnl += t.pnl
            
            if t.pnl > 0: wins += 1
            else: losses += 1
            
            # Aggregations
            strategy_pnl[t.strategy] += t.pnl
            regime_pnl[t.regime] += t.pnl
            
            # Extremes
            if not best_trade or t.pnl > best_trade.pnl:
                best_trade = t
            if not worst_trade or t.pnl < worst_trade.pnl:
                worst_trade = t
                
        total_closed = wins + losses
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        
        report = {
            "total_trades": total_closed,
            "net_pnl": round(total_pnl, 2),
            "win_rate": round(win_rate, 1),
            "best_strategy": max(strategy_pnl, key=strategy_pnl.get, default="None"),
            "worst_strategy": min(strategy_pnl, key=strategy_pnl.get, default="None"),
            "best_regime": max(regime_pnl, key=regime_pnl.get, default="None"),
            "worst_regime": min(regime_pnl, key=regime_pnl.get, default="None"),
            "leak_analysis": dict(regime_pnl)
        }
        
        self.logger.info(f"📊 Weekly Review: PnL {total_pnl:.2f} | Win {win_rate}%")
        return report

# Singleton
weekly_review = WeeklyReview()

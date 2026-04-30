"""
Performance Reporter
Calculates Key Performance Indicators (KPIs) for the backtest.
"""
import logging
import pandas as pd
import numpy as np
from typing import List, Dict

class PerformanceReporter:
    """
    Generates performance metrics.
    """
    def __init__(self, initial_capital: float):
        self.logger = logging.getLogger("Reporter")
        self.initial_capital = initial_capital
        self.equity_curve: List[Dict] = []
        
    def record_day(self, timestamp: any, equity: float):
        """Record equity state."""
        self.equity_curve.append({
            "timestamp": timestamp,
            "equity": equity
        })
        
    def generate_report(self) -> Dict:
        """Calculate CAGR, Drawdown, Sharpe."""
        if not self.equity_curve:
            return {"status": "No Data"}
            
        df = pd.DataFrame(self.equity_curve)
        
        # Total Return
        final_equity = df.iloc[-1]['equity']
        total_return = ((final_equity - self.initial_capital) / self.initial_capital) * 100
        
        # Drawdown
        df['peak'] = df['equity'].cummax()
        df['drawdown'] = (df['equity'] - df['peak']) / df['peak']
        max_drawdown = df['drawdown'].min() * 100 # Convert to %
        
        # Simple Sharpe (Daily returns)
        # Assuming daily data points. If intraday, this needs resampling.
        # Calculating returns based on whatever step periodicity was recorded.
        df['returns'] = df['equity'].pct_change().fillna(0)
        mean_ret = df['returns'].mean()
        std_ret = df['returns'].std()
        
        # Annualized Sharpe (assuming 252 steps if daily, simplified)
        sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret != 0 else 0.0
        
        report = {
            "initial_capital": self.initial_capital,
            "final_equity": round(final_equity, 2),
            "total_return_pct": round(total_return, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 2)
        }
        
        self.logger.info("📊 --- BACKTEST REPORT ---")
        self.logger.info(f"Return: {report['total_return_pct']}%")
        self.logger.info(f"Max DD: {report['max_drawdown_pct']}%")
        self.logger.info(f"Sharpe: {report['sharpe_ratio']}")
        
        return report

"""
Execution Quality Monitor
Tracks slippage and fill quality metrics.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class ExecutionRecord:
    symbol: str
    strategy: str
    urgency: str
    expected_price: float
    fill_price: float
    slippage: float
    slippage_pct: float
    timestamp: int

class ExecutionQualityMonitor:
    """
    Monitors execution quality.
    
    Metrics:
    - Average Slippage (pts)
    - Average Slippage (%)
    - Negative Slippage Frequency
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ExecutionQualityMonitor")
        self.records: List[ExecutionRecord] = []
        
    def record_execution(
        self,
        symbol: str, 
        action: str,
        expected_price: float,
        fill_price: float,
        urgency: str
    ):
        """Record trade execution details."""
        if expected_price <= 0:
            return  # Can't calc slippage without expected price
            
        if action == "BUY":
            slippage = fill_price - expected_price  # Positive is bad for buy
        else:
            slippage = expected_price - fill_price  # Positive is bad for sell
            
        # If fill is better than expected (Negative slippage), that's good!
        # But commonly "Slippage" implies bad. 
        # Let's standardize: Positive = Cost (Bad), Negative = Improvement (Good)
        
        slippage_pct = (slippage / expected_price) * 100
        
        import time
        record = ExecutionRecord(
            symbol=symbol,
            strategy="UNKNOWN",
            urgency=urgency,
            expected_price=expected_price,
            fill_price=fill_price,
            slippage=slippage,
            slippage_pct=slippage_pct,
            timestamp=int(time.time())
        )
        
        self.records.append(record)
        
        self.logger.info(
            f"📊 Execution Quality: {symbol} | Urgency: {urgency} | "
            f"Slippage: {slippage:+.2f} ({slippage_pct:+.2f}%)"
        )
        
    def get_stats(self) -> Dict:
        """Get aggregate stats."""
        if not self.records:
            return {"count": 0}
            
        total_slippage = sum(r.slippage for r in self.records)
        avg_slippage = total_slippage / len(self.records)
        
        return {
            "count": len(self.records),
            "total_slippage": round(total_slippage, 2),
            "avg_slippage": round(avg_slippage, 2),
            "last_fill": self.records[-1] if self.records else None
        }

# Singleton
execution_quality_monitor = ExecutionQualityMonitor()

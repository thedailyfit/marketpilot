"""
IV Trend Engine
Detects whether Implied Volatility is EXPANDING, STABLE, or CONTRACTING.
Uses historical IV time-series to compute trend slope.
"""
import logging
import statistics
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum

class TrendDirection(Enum):
    RISING = "RISING"       # IV Expansion
    FLAT = "FLAT"           # Stable
    FALLING = "FALLING"     # IV Contraction/Crush

@dataclass
class IVTrendResult:
    trend: TrendDirection
    slope: float
    strength: float         # 0.0 to 1.0 (confidence/magnitude)
    explanation: str

class IVTrendEngine:
    """
    Analyzes IV time-series to determine trend.
    """
    def __init__(self, lookback_window: int = 20, threshold: float = 0.0005):
        """
        Args:
            lookback_window: Number of data points to consider (e.g., 20 candles).
            threshold: Slope threshold for RISING/FALLING classification.
                       0.0005 means ~0.05% IV change per period (x100 for percentage points).
                       Adjust based on IV scale (0.15 vs 15.0). Assuming decimal IV (0.15).
        """
        self.logger = logging.getLogger("IVTrendEngine")
        self.lookback_window = lookback_window
        self.threshold = threshold

    def analyze(self, iv_series: List[float]) -> IVTrendResult:
        """
        Analyze a list of historical IV values (ordered roughly old -> new).
        
        Args:
            iv_series: List of IV floats (e.g., [0.14, 0.142, 0.145...])
                       Assumes decimal format (0.15 = 15%).
        """
        if not iv_series or len(iv_series) < 3:
            return IVTrendResult(TrendDirection.FLAT, 0.0, 0.0, "Insufficient data")
            
        # Use simple linear regression for slope
        # y = mx + c
        # We only care about 'm' (slope)
        
        n = len(iv_series)
        x = range(n)
        y = iv_series
        
        # Calculate slope
        mean_x = statistics.mean(x)
        mean_y = statistics.mean(y)
        
        # Slope = sum((x - mean_x) * (y - mean_y)) / sum((x - mean_x)^2)
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        denominator = sum((xi - mean_x) ** 2 for xi in x)
        
        slope = numerator / denominator if denominator != 0 else 0.0
        
        # Classify Trend
        # Slope represents change in IV per period.
        # E.g., if IV goes 0.15 -> 0.16 over 10 periods, slope is 0.001.
        
        trend = TrendDirection.FLAT
        strength = min(1.0, abs(slope) / (self.threshold * 10)) # Normalize strength roughly
        
        if slope > self.threshold:
            trend = TrendDirection.RISING
        elif slope < -self.threshold:
            trend = TrendDirection.FALLING
            
        # Explanation
        direction_str = "EXPANDING" if trend == TrendDirection.RISING else \
                        "CONTRACTING" if trend == TrendDirection.FALLING else "STABLE"
                        
        explanation = (
            f"IV is {direction_str} (Slope: {slope:.6f}). "
            f"Changed from {y[0]:.4f} to {y[-1]:.4f} over {n} periods."
        )
            
        return IVTrendResult(
            trend=trend,
            slope=slope,
            strength=strength,
            explanation=explanation
        )

# Singleton
iv_trend_engine = IVTrendEngine()

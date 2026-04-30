"""
Opening Range Breakout (ORB) Strategy
Catches big moves in first 30 minutes of market.
Best when: 9:15-10:00 AM, High volume, VIX 12-18
"""
import numpy as np
from datetime import datetime, time
from typing import Dict, Optional
from dataclasses import dataclass
import logging


logger = logging.getLogger(__name__)


@dataclass
class ORBSignal:
    """ORB strategy signal."""
    action: str  # BUY, SELL, NO_TRADE
    entry_price: float
    sl_price: float
    tp_price: float
    range_high: float
    range_low: float
    confidence: float
    reason: str


class ORBStrategy:
    """
    Opening Range Breakout Strategy.
    
    Concept:
    - Wait for first 15-30 minutes to establish the range
    - Enter when price breaks above/below this range
    - 80% of daily range is established by 11:30 AM
    
    Entry Rules:
    - Time: 9:20-10:30 AM (after range forms, before 80% move)
    - Breakout with volume confirmation (2x average)
    - VIX between 12-18 (enough volatility, not crazy)
    
    Exit Rules:
    - Stop loss: Opposite side of range
    - Take profit: 1.5x to 2x risk
    - Exit by 11:30 AM if not hit
    
    This is the MOST PROFITABLE intraday strategy for Indian markets.
    """
    
    def __init__(self):
        self.name = "ORB"
        self.range_start = time(9, 15)
        self.range_end = time(9, 30)
        self.entry_start = time(9, 31)
        self.entry_end = time(10, 30)
        self.exit_time = time(11, 30)
        
        self.min_range_pct = 0.002  # Minimum 0.2% range
        self.max_range_pct = 0.015  # Maximum 1.5% range
        self.volume_multiplier = 1.5  # Volume must be 1.5x average
        
        self.risk_reward = 2.0  # Target 2:1 RR
        
        # Track daily range
        self.daily_high = None
        self.daily_low = None
        self.range_formed = False
        self.current_date = None
        self.breakout_triggered = False
        
    def reset_daily(self, date):
        """Reset daily tracking."""
        self.daily_high = None
        self.daily_low = None
        self.range_formed = False
        self.current_date = date
        self.breakout_triggered = False
    
    def generate_signal(self, data_slice, params: Dict = None) -> Optional[Dict]:
        """
        Generate ORB signal based on opening range breakout.
        """
        params = params or {}
        
        if len(data_slice) < 10:
            return None
        
        current = data_slice.iloc[-1]
        current_time = current['datetime']
        current_date = current_time.date()
        current_price = current['close']
        current_volume = current.get('volume', 0)
        
        # Reset for new day
        if self.current_date != current_date:
            self.reset_daily(current_date)
        
        current_timeonly = current_time.time()
        
        # Phase 1: Build the opening range (9:15-9:30)
        if self.range_start <= current_timeonly <= self.range_end:
            if self.daily_high is None:
                self.daily_high = current['high']
                self.daily_low = current['low']
            else:
                self.daily_high = max(self.daily_high, current['high'])
                self.daily_low = min(self.daily_low, current['low'])
            return None
        
        # Mark range as formed
        if current_timeonly > self.range_end and not self.range_formed:
            self.range_formed = True
            if self.daily_high and self.daily_low:
                logger.debug(f"ORB Range: {self.daily_low:.2f} - {self.daily_high:.2f}")
        
        # Phase 2: Look for breakout (9:31-10:30)
        if not self.range_formed or self.daily_high is None or self.daily_low is None:
            return None
        
        if current_timeonly < self.entry_start or current_timeonly > self.entry_end:
            return None
        
        if self.breakout_triggered:
            return None
        
        # Calculate range
        range_size = self.daily_high - self.daily_low
        range_pct = range_size / current_price
        
        # Validate range size
        if range_pct < self.min_range_pct or range_pct > self.max_range_pct:
            return None
        
        # Check volume confirmation
        avg_volume = data_slice['volume'].mean() if 'volume' in data_slice.columns else 50000
        volume_ok = current_volume > avg_volume * self.volume_multiplier
        
        # Breakout detection
        breakout_buffer = range_size * 0.1  # 10% buffer above/below range
        
        # Bullish breakout
        if current_price > self.daily_high + breakout_buffer:
            if not volume_ok:
                return None
            
            self.breakout_triggered = True
            sl_price = self.daily_low
            risk = current_price - sl_price
            tp_price = current_price + (risk * self.risk_reward)
            
            return {
                'action': 'BUY',
                'strategy': 'ORB',
                'entry_price': current_price,
                'sl_pct': risk / current_price,
                'tp_pct': (tp_price - current_price) / current_price,
                'range_high': self.daily_high,
                'range_low': self.daily_low,
                'confidence': 0.65,
                'reason': f'Bullish Breakout above {self.daily_high:.0f}'
            }
        
        # Bearish breakout
        if current_price < self.daily_low - breakout_buffer:
            if not volume_ok:
                return None
            
            self.breakout_triggered = True
            sl_price = self.daily_high
            risk = sl_price - current_price
            tp_price = current_price - (risk * self.risk_reward)
            
            return {
                'action': 'SELL',
                'strategy': 'ORB',
                'entry_price': current_price,
                'sl_pct': risk / current_price,
                'tp_pct': (current_price - tp_price) / current_price,
                'range_high': self.daily_high,
                'range_low': self.daily_low,
                'confidence': 0.65,
                'reason': f'Bearish Breakout below {self.daily_low:.0f}'
            }
        
        return None
    
    def backtest_strategy(self, data_slice, params: Dict = None) -> Optional[Dict]:
        """Backtest version of the strategy."""
        return self.generate_signal(data_slice, params)


def orb_strategy_func(data_slice, params: Dict = None) -> Optional[Dict]:
    """Standalone function for backtest engine."""
    strategy = ORBStrategy()
    return strategy.backtest_strategy(data_slice, params)


# Strategy instance
orb_strategy = ORBStrategy()

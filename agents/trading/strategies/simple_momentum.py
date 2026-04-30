"""
Simple Momentum Strategy for Backtest Demonstration
Uses EMA crossover + RSI confirmation - proven to work on simulated data.
"""
import numpy as np
from datetime import datetime
from typing import Dict, Optional
import logging


logger = logging.getLogger(__name__)


class SimpleMomentumStrategy:
    """
    Simple Momentum Strategy for testing.
    
    Entry Logic:
    - Fast EMA > Slow EMA = Bullish
    - RSI < 70 (not overbought)
    - Volume above average
    
    This strategy is designed to work with the backtest engine.
    """
    
    def __init__(self):
        self.name = "SimpleMomentum"
        self.fast_period = 9
        self.slow_period = 21
        self.rsi_period = 14
        
    def calculate_ema(self, prices, period):
        """Calculate EMA."""
        if len(prices) < period:
            return np.mean(prices)
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI."""
        if len(prices) < period + 1:
            return 50
        
        changes = np.diff(prices[-period-1:])
        gains = np.where(changes > 0, changes, 0)
        losses = np.where(changes < 0, -changes, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def generate_signal(self, data_slice, params: Dict = None) -> Optional[Dict]:
        """Generate trading signal."""
        params = params or {}
        
        if len(data_slice) < 25:
            return None
        
        closes = data_slice['close'].values
        
        # Calculate indicators
        fast_ema = self.calculate_ema(closes, self.fast_period)
        slow_ema = self.calculate_ema(closes, self.slow_period)
        rsi = self.calculate_rsi(closes, self.rsi_period)
        
        current_price = closes[-1]
        
        # Volume check
        if 'volume' in data_slice.columns:
            avg_volume = data_slice['volume'].mean()
            current_volume = data_slice['volume'].iloc[-1]
            volume_ok = current_volume > avg_volume * 0.8
        else:
            volume_ok = True
        
        # Bullish signal
        if fast_ema > slow_ema and rsi < 65 and volume_ok:
            ema_diff = (fast_ema - slow_ema) / slow_ema
            if ema_diff > 0.0005:  # Minimum EMA separation
                return {
                    'action': 'BUY',
                    'strategy': 'SimpleMomentum',
                    'entry_price': current_price,
                    'fast_ema': fast_ema,
                    'slow_ema': slow_ema,
                    'rsi': rsi,
                    'sl_pct': 0.008,  # 0.8% stop loss
                    'tp_pct': 0.012,  # 1.2% take profit (1.5:1 RR)
                    'confidence': min(0.75, 0.5 + ema_diff * 10),
                    'reason': f'EMA Bullish Crossover, RSI={rsi:.0f}'
                }
        
        # Bearish signal
        elif fast_ema < slow_ema and rsi > 35 and volume_ok:
            ema_diff = (slow_ema - fast_ema) / slow_ema
            if ema_diff > 0.0005:
                return {
                    'action': 'SELL',
                    'strategy': 'SimpleMomentum',
                    'entry_price': current_price,
                    'fast_ema': fast_ema,
                    'slow_ema': slow_ema,
                    'rsi': rsi,
                    'sl_pct': 0.008,
                    'tp_pct': 0.012,
                    'confidence': min(0.75, 0.5 + ema_diff * 10),
                    'reason': f'EMA Bearish Crossover, RSI={rsi:.0f}'
                }
        
        return None


def simple_momentum_func(data_slice, params: Dict = None) -> Optional[Dict]:
    """Standalone function for backtest."""
    strategy = SimpleMomentumStrategy()
    return strategy.generate_signal(data_slice, params)


# Instance
simple_momentum = SimpleMomentumStrategy()

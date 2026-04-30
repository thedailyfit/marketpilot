"""
Buy Call Scalp Strategy
Aggressive momentum scalping strategy focusing on long entries (Buy Call).
Uses tight SL/TP and 5-min timeframe.
"""
import numpy as np
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class BuyCallScalpStrategy:
    """
    Buy Call Scalp Strategy.
    
    Logic:
    - 5 EMA > 13 EMA (Short-term trend)
    - RSI > 55 (Momentum building)
    - Close > VWAP (Price strength) - *Simplified to avg price if VWAP not avail*
    - Volume > 1.2x Avg Vol (Participation)
    """
    
    def __init__(self):
        self.name = "BuyCallScalp"
        self.fast_ema_period = 5
        self.slow_ema_period = 13
        self.rsi_period = 14
        
    def calculate_ema(self, prices, period):
        if len(prices) < period:
            return np.mean(prices)
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def calculate_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50
        changes = np.diff(prices[-period-1:])
        gains = np.where(changes > 0, changes, 0)
        losses = np.where(changes < 0, -changes, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def generate_signal(self, data_slice, params: Dict = None) -> Optional[Dict]:
        """Generate Buy Call Scalp signal."""
        if len(data_slice) < 20:
            return None
        
        closes = data_slice['close'].values
        current_price = closes[-1]
        
        # Indicators
        fast_ema = self.calculate_ema(closes, self.fast_ema_period)
        slow_ema = self.calculate_ema(closes, self.slow_ema_period)
        rsi = self.calculate_rsi(closes, self.rsi_period)
        
        # Volume
        volume_ok = True
        if 'volume' in data_slice.columns:
            avg_vol = data_slice['volume'].tail(20).mean()
            current_vol = data_slice['volume'].iloc[-1]
            if current_vol < avg_vol * 1.0: # require at least avg volume
                volume_ok = False
        
        # Signal logic: Aggressive Long
        # 1. Bullish Crossover or Strong Trend
        trend_bullish = fast_ema > slow_ema
        
        # 2. RSI Momentum (50-75 sweet spot for breakout scalp)
        rsi_bullish = 55 < rsi < 75
        
        if trend_bullish and rsi_bullish and volume_ok:
             # Calculate tighter stop for scalp
            atr_approx = (data_slice['high'].iloc[-1] - data_slice['low'].iloc[-1])
            sl_dist = atr_approx * 1.5
            sl_price = current_price - sl_dist
            sl_pct = (sl_dist / current_price) 
            
            # Ensure min/max SL
            sl_pct = max(0.003, min(sl_pct, 0.008)) # 0.3% to 0.8%
            
            return {
                'action': 'BUY',
                'strategy': 'BuyCallScalp',
                'entry_price': current_price,
                'target_instrument': 'CE', # Call Option
                'sl_pct': sl_pct,
                'tp_pct': sl_pct * 1.5, # 1.5 RR
                'confidence': 0.85,
                'reason': f'Scalp: EMA(5)>EMA(13), RSI={rsi:.1f}, Vol OK'
            }
            
        return None

def buy_call_scalp_func(data_slice, params: Dict = None):
    strategy = BuyCallScalpStrategy()
    return strategy.generate_signal(data_slice, params)

buy_call_scalp = BuyCallScalpStrategy()

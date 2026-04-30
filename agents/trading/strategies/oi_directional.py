"""
OI-Based Directional Strategy
Follows institutional money flow using Open Interest analysis.
Best when: PCR extreme (>1.3 or <0.7), FII/DII data confirms
"""
import numpy as np
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass
import logging


logger = logging.getLogger(__name__)


@dataclass
class OISignal:
    """OI-based strategy signal."""
    action: str  # BUY, SELL, NO_TRADE
    pcr: float
    call_oi_change: int
    put_oi_change: int
    max_pain: float
    confidence: float
    reason: str


class OIDirectionalStrategy:
    """
    Open Interest Based Directional Strategy.
    
    Concept:
    - PCR > 1.2 = Bullish (put writers confident)
    - PCR < 0.8 = Bearish (call writers confident)
    - Follow the "smart money" (FIIs)
    
    Key Signals:
    1. PCR Extreme: >1.3 very bullish, <0.7 very bearish
    2. Max Pain Theory: Price tends to move towards max pain by expiry
    3. OI Build-up: Large OI addition = support/resistance
    4. OI Unwinding: Large OI reduction = trend continuation
    
    Entry Rules:
    - PCR crosses extreme threshold
    - OI change confirms direction
    - Not against max pain trend
    
    Exit Rules:
    - PCR returns to normal (0.9-1.1)
    - Max pain reached
    - Expiry (theta decay risk)
    """
    
    def __init__(self):
        self.name = "OIDirectional"
        
        # PCR thresholds
        self.pcr_very_bullish = 1.3
        self.pcr_bullish = 1.2
        self.pcr_bearish = 0.8
        self.pcr_very_bearish = 0.7
        self.pcr_neutral_low = 0.9
        self.pcr_neutral_high = 1.1
        
        # Simulated PCR (in real trading, fetch from option chain)
        self.simulated_pcr = 1.0
        
    def calculate_pcr(self, data_slice, params: Dict = None) -> float:
        """
        Calculate PCR from data or simulation.
        In production, this would fetch real option chain data.
        """
        params = params or {}
        
        # If PCR provided in params, use it
        if 'pcr' in params:
            return params['pcr']
        
        # Simulate PCR based on price action
        # When price is falling, puts get bought (PCR rises)
        # When price is rising, calls get bought (PCR falls)
        
        if len(data_slice) < 10:
            return 1.0
        
        returns = data_slice['close'].pct_change().dropna()
        cumulative_return = (1 + returns).prod() - 1
        
        # Simulate PCR response to price movement
        base_pcr = 1.0
        pcr_adjustment = -cumulative_return * 10  # Inverse relationship
        simulated_pcr = base_pcr + pcr_adjustment
        
        # Add some randomness for realism
        noise = np.random.normal(0, 0.05)
        simulated_pcr += noise
        
        # Bound PCR to realistic range
        return max(0.5, min(2.0, simulated_pcr))
    
    def calculate_max_pain(self, current_price: float, params: Dict = None) -> float:
        """
        Calculate max pain price.
        In production, this would analyze full option chain.
        """
        params = params or {}
        
        if 'max_pain' in params:
            return params['max_pain']
        
        # Simulate max pain near current price (typically within 1%)
        offset = np.random.uniform(-0.01, 0.01)
        return current_price * (1 + offset)
    
    def generate_signal(self, data_slice, params: Dict = None) -> Optional[Dict]:
        """
        Generate OI-based directional signal.
        """
        params = params or {}
        
        if len(data_slice) < 20:
            return None
        
        current = data_slice.iloc[-1]
        current_price = current['close']
        current_time = current['datetime']
        
        # Avoid expiry day (Thursday typically)
        if current_time.weekday() == 3:
            return None
        
        # Calculate PCR
        pcr = self.calculate_pcr(data_slice, params)
        
        # No trade in neutral zone
        if self.pcr_neutral_low <= pcr <= self.pcr_neutral_high:
            return None
        
        # Calculate max pain
        max_pain = self.calculate_max_pain(current_price, params)
        
        # Simulate OI changes
        call_oi_change = int(np.random.normal(0, 50000))
        put_oi_change = int(np.random.normal(0, 50000))
        
        # Very Bullish Signal
        if pcr >= self.pcr_very_bullish:
            # Strong put writing = very bullish
            confidence = min(0.8, 0.5 + (pcr - 1.2) * 0.5)
            
            return {
                'action': 'BUY',
                'strategy': 'OIDirectional',
                'pcr': pcr,
                'call_oi_change': call_oi_change,
                'put_oi_change': put_oi_change,
                'max_pain': max_pain,
                'sl_pct': 0.015,  # 1.5% SL
                'tp_pct': 0.02,   # 2% TP
                'confidence': confidence,
                'reason': f'Very Bullish PCR ({pcr:.2f}), Heavy Put Writing'
            }
        
        # Bullish Signal
        elif pcr >= self.pcr_bullish:
            return {
                'action': 'BUY',
                'strategy': 'OIDirectional',
                'pcr': pcr,
                'call_oi_change': call_oi_change,
                'put_oi_change': put_oi_change,
                'max_pain': max_pain,
                'sl_pct': 0.01,
                'tp_pct': 0.015,
                'confidence': 0.55,
                'reason': f'Bullish PCR ({pcr:.2f})'
            }
        
        # Very Bearish Signal
        elif pcr <= self.pcr_very_bearish:
            confidence = min(0.8, 0.5 + (0.8 - pcr) * 0.5)
            
            return {
                'action': 'SELL',
                'strategy': 'OIDirectional',
                'pcr': pcr,
                'call_oi_change': call_oi_change,
                'put_oi_change': put_oi_change,
                'max_pain': max_pain,
                'sl_pct': 0.015,
                'tp_pct': 0.02,
                'confidence': confidence,
                'reason': f'Very Bearish PCR ({pcr:.2f}), Heavy Call Writing'
            }
        
        # Bearish Signal
        elif pcr <= self.pcr_bearish:
            return {
                'action': 'SELL',
                'strategy': 'OIDirectional',
                'pcr': pcr,
                'call_oi_change': call_oi_change,
                'put_oi_change': put_oi_change,
                'max_pain': max_pain,
                'sl_pct': 0.01,
                'tp_pct': 0.015,
                'confidence': 0.55,
                'reason': f'Bearish PCR ({pcr:.2f})'
            }
        
        return None
    
    def backtest_strategy(self, data_slice, params: Dict = None) -> Optional[Dict]:
        """Backtest version of the strategy."""
        return self.generate_signal(data_slice, params)


def oi_directional_strategy_func(data_slice, params: Dict = None) -> Optional[Dict]:
    """Standalone function for backtest engine."""
    strategy = OIDirectionalStrategy()
    return strategy.backtest_strategy(data_slice, params)


# Strategy instance
oi_directional_strategy = OIDirectionalStrategy()

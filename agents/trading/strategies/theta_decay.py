"""
Theta Decay Strategy (Iron Condor / Short Straddle)
Sells premium and profits from time decay.
Best when: VIX > 13, Time > 2PM, Non-expiry days
"""
import numpy as np
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass
import logging


logger = logging.getLogger(__name__)


@dataclass
class ThetaSignal:
    """Theta strategy signal."""
    action: str  # SELL_STRADDLE, SELL_STRANGLE, NO_TRADE
    strike: float
    premium_collected: float
    max_loss: float
    sl_pct: float
    tp_pct: float
    confidence: float
    reason: str


class ThetaDecayStrategy:
    """
    Theta Decay Strategy - Sells options premium.
    
    Variants:
    1. Iron Condor: Sell OTM calls & puts, buy further OTM for protection
    2. Short Straddle: Sell ATM call & put (higher premium, higher risk)
    3. Short Strangle: Sell OTM call & put (lower premium, lower risk)
    
    Entry Rules:
    - VIX > 13 (enough premium to collect)
    - Time > 2:00 PM (theta accelerates)
    - Not on expiry day (gamma risk too high)
    - IV Percentile > 50% (sell when IV is high)
    
    Exit Rules:
    - Take profit at 50% of premium collected
    - Stop loss at 100% of premium (2:1 loss possible)
    - Exit by 3:10 PM (before close volatility)
    """
    
    def __init__(self):
        self.name = "ThetaDecay"
        self.min_vix = 13.0
        self.max_vix = 25.0
        self.min_time_hour = 14  # 2:00 PM
        self.tp_pct = 0.5  # 50% of premium
        self.sl_pct = 1.0  # 100% of premium (double loss)
        
    def generate_signal(self, data_slice, params: Dict = None) -> Optional[Dict]:
        """
        Generate theta decay signal.
        
        For backtesting, we simulate the strategy conditions.
        """
        params = params or {}
        
        if len(data_slice) < 5:
            return None
        
        current = data_slice.iloc[-1]
        current_time = current['datetime']
        current_price = current['close']
        
        # Time filter - only trade after 2 PM
        if current_time.hour < self.min_time_hour:
            return None
        
        # VIX simulation (in real trading, fetch from API)
        simulated_vix = params.get('vix', 15.0)
        if simulated_vix < self.min_vix or simulated_vix > self.max_vix:
            return None
        
        # Day of week filter - avoid expiry days
        day = current_time.weekday()
        if day == 3:  # Thursday (Nifty expiry)
            return None
        
        # Calculate recent volatility
        returns = data_slice['close'].pct_change().dropna()
        recent_volatility = returns.std() * np.sqrt(252 * 75)  # Annualized
        
        # Only sell if volatility is reasonable (not too low, not too high)
        if recent_volatility < 0.08 or recent_volatility > 0.35:
            return None
        
        # Check for ranging market (good for theta strategies)
        high = data_slice['high'].max()
        low = data_slice['low'].min()
        range_pct = (high - low) / current_price
        
        if range_pct > 0.015:  # If range > 1.5%, market trending - skip
            return None
        
        # Premium estimation (simplified)
        estimated_premium = current_price * 0.005  # ~0.5% of spot
        
        # Generate signal with PROPER risk management
        # Key: SL should be wider than TP for theta (we win more often but smaller)
        return {
            'action': 'SELL',  # Sell options (collect premium)
            'strategy': 'ThetaDecay',
            'strike': current_price,
            'premium': estimated_premium,
            'sl_pct': 0.015,  # 1.5% stop loss (wider)
            'tp_pct': 0.008,  # 0.8% take profit (collect premium)
            'confidence': 0.7,
            'reason': f'High IV ({simulated_vix:.1f}), Ranging Market, Time {current_time.strftime("%H:%M")}'
        }
    
    def backtest_strategy(self, data_slice, params: Dict = None) -> Optional[Dict]:
        """Backtest version of the strategy."""
        return self.generate_signal(data_slice, params)


def theta_decay_strategy_func(data_slice, params: Dict = None) -> Optional[Dict]:
    """Standalone function for backtest engine."""
    strategy = ThetaDecayStrategy()
    return strategy.backtest_strategy(data_slice, params)


# Strategy instance
theta_strategy = ThetaDecayStrategy()

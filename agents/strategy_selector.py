"""
Multi-Strategy Selector Agent
Runs all 3 strategies simultaneously and picks the best one based on market conditions.
"""
import asyncio
from datetime import datetime, time
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
import logging
import numpy as np

from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from agents.trading.strategies.theta_decay import ThetaDecayStrategy, theta_strategy
from agents.trading.strategies.orb import ORBStrategy, orb_strategy
from agents.trading.strategies.oi_directional import OIDirectionalStrategy, oi_directional_strategy
from agents.trading.strategies.buy_call_scalp import BuyCallScalpStrategy, buy_call_scalp_func


logger = logging.getLogger(__name__)


@dataclass
class MarketRegime:
    """Current market regime classification."""
    regime_type: str  # TRENDING, RANGING, VOLATILE, QUIET
    vix_level: float
    pcr: float
    intraday_range_pct: float
    time_of_day: str  # MORNING, MIDDAY, AFTERNOON, CLOSE
    day_type: str  # EXPIRY, PRE_EXPIRY, NORMAL
    recommended_strategies: List[str] = field(default_factory=list)


@dataclass
class StrategyScore:
    """Score for each strategy based on current conditions."""
    strategy_name: str
    base_score: float  # Historical win rate
    condition_score: float  # How well current conditions match
    final_score: float
    reasons: List[str] = field(default_factory=list)


class StrategySelector(BaseAgent):
    """
    Multi-Strategy Selector Agent.
    
    Runs all 3 strategies in parallel and selects the best one
    based on current market conditions:
    
    1. Theta Decay (Iron Condor)
       - Best when: VIX > 13, Time > 2PM, Ranging market
       - Avoid: Expiry day, trending days
    
    2. ORB Breakout
       - Best when: 9:20-10:30 AM, High volume, Clear range
       - Avoid: Afternoon, low volatility days
    
    3. OI Directional
       - Best when: PCR extreme, Strong FII/DII bias
       - Avoid: Neutral PCR, conflicting signals
    
    Selection Algorithm:
    1. Classify current market regime
    2. Score each strategy based on conditions
    3. Filter strategies that match regime
    4. Pick highest scoring strategy
    5. Generate unified signal
    """
    
    def __init__(self):
        super().__init__("StrategySelector")
        
        # Strategy instances
        self.theta_strategy = ThetaDecayStrategy()
        self.orb_strategy = ORBStrategy()
        self.oi_strategy = OIDirectionalStrategy()
        self.buy_call_strategy = BuyCallScalpStrategy() # [NEW]
        
        # Strategy base scores (from historical backtests)
        self.base_scores = {
            'ThetaDecay': 0.70,
            'ORB': 0.55,
            'OIDirectional': 0.60,
            'BuyCallScalp': 0.65 # [NEW]
        }
        
        # Current market state
        self.current_regime: Optional[MarketRegime] = None
        self.last_signal_time: Optional[datetime] = None
        self.min_signal_gap_minutes = 30  # No signals within 30 mins
        
        # Performance tracking
        self.strategy_performance = {
            'ThetaDecay': {'wins': 0, 'losses': 0, 'pnl': 0},
            'ORB': {'wins': 0, 'losses': 0, 'pnl': 0},
            'OIDirectional': {'wins': 0, 'losses': 0, 'pnl': 0},
            'BuyCallScalp': {'wins': 0, 'losses': 0, 'pnl': 0}
        }
        
        # VIX and PCR (will be updated from real data)
        self.current_vix = 15.0
        self.current_pcr = 1.0
        
    async def on_start(self):
        """Start the strategy selector."""
        self.logger.info("Strategy Selector Agent Started")
        self.logger.info("Monitoring: ThetaDecay | ORB | OIDirectional | BuyCallScalp")
        
        # Subscribe to market data events
        bus.subscribe(EventType.TICK, self._on_tick)
        
    async def on_stop(self):
        """Stop the strategy selector."""
        self.logger.info("Strategy Selector Agent Stopped")
        self._print_performance_summary()
    
    def _on_tick(self, data: dict):
        """Handle incoming tick data."""
        # Update VIX if available
        if 'vix' in data:
            self.current_vix = data['vix']
        
        # Update PCR if available
        if 'pcr' in data:
            self.current_pcr = data['pcr']
    
    def classify_regime(self, data_slice, current_time: datetime) -> MarketRegime:
        """
        Classify current market regime based on multiple factors.
        """
        # Calculate metrics
        if len(data_slice) < 5:
            return MarketRegime(
                regime_type='UNKNOWN',
                vix_level=self.current_vix,
                pcr=self.current_pcr,
                intraday_range_pct=0,
                time_of_day='UNKNOWN',
                day_type='NORMAL',
                recommended_strategies=[]
            )
        
        # Intraday range
        high = data_slice['high'].max()
        low = data_slice['low'].min()
        current_price = data_slice['close'].iloc[-1]
        range_pct = (high - low) / current_price
        
        # Time classification
        hour = current_time.hour + current_time.minute / 60
        if hour < 10:
            time_of_day = 'MORNING'
        elif hour < 12.5:
            time_of_day = 'MIDDAY'
        elif hour < 14.5:
            time_of_day = 'AFTERNOON'
        else:
            time_of_day = 'CLOSE'
        
        # Day type
        weekday = current_time.weekday()
        if weekday == 3:  # Thursday
            day_type = 'EXPIRY'
        elif weekday == 2:  # Wednesday
            day_type = 'PRE_EXPIRY'
        else:
            day_type = 'NORMAL'
        
        # Regime classification
        if self.current_vix > 20:
            regime_type = 'VOLATILE'
        elif self.current_vix < 12:
            regime_type = 'QUIET'
        elif range_pct > 0.012:
            regime_type = 'TRENDING'
        else:
            regime_type = 'RANGING'
        
        # Recommend strategies based on regime
        recommended = []
        
        if regime_type == 'RANGING' and time_of_day in ['AFTERNOON', 'CLOSE']:
            recommended.append('ThetaDecay')
        
        if time_of_day == 'MORNING' and regime_type != 'QUIET':
            recommended.append('ORB')
        
        if abs(self.current_pcr - 1.0) > 0.2:  # PCR outside 0.8-1.2
            recommended.append('OIDirectional')
            
        if self.current_vix > 12 and regime_type in ['TRENDING', 'VOLATILE']:
            recommended.append('BuyCallScalp')
        
        return MarketRegime(
            regime_type=regime_type,
            vix_level=self.current_vix,
            pcr=self.current_pcr,
            intraday_range_pct=range_pct,
            time_of_day=time_of_day,
            day_type=day_type,
            recommended_strategies=recommended
        )
    
    def score_strategy(
        self, 
        strategy_name: str, 
        regime: MarketRegime
    ) -> StrategyScore:
        """
        Score a strategy based on current market conditions.
        """
        base_score = self.base_scores.get(strategy_name, 0.5)
        condition_score = 0.0
        reasons = []
        
        if strategy_name == 'ThetaDecay':
            # Theta works best in ranging markets, afternoon, no expiry
            if regime.regime_type == 'RANGING':
                condition_score += 0.3
                reasons.append("Ranging market ideal for theta")
            
            if regime.time_of_day in ['AFTERNOON', 'CLOSE']:
                condition_score += 0.2
                reasons.append("Afternoon theta acceleration")
            
            if regime.vix_level > 13:
                condition_score += 0.2
                reasons.append(f"VIX {regime.vix_level:.1f} = good premium")
            
            if regime.day_type == 'EXPIRY':
                condition_score -= 0.3
                reasons.append("Expiry day risky for theta")
                
        elif strategy_name == 'ORB':
            # ORB works best in morning with volatility
            if regime.time_of_day == 'MORNING':
                condition_score += 0.4
                reasons.append("Morning = ORB prime time")
            
            if regime.intraday_range_pct > 0.003:
                condition_score += 0.2
                reasons.append("Good opening range formed")
            
            if 12 <= regime.vix_level <= 18:
                condition_score += 0.15
                reasons.append("VIX in sweet spot for breakouts")
            
            if regime.time_of_day in ['AFTERNOON', 'CLOSE']:
                condition_score -= 0.4
                reasons.append("Too late for ORB")
                
        elif strategy_name == 'OIDirectional':
            # OI works best with extreme PCR
            pcr_deviation = abs(regime.pcr - 1.0)
            
            if pcr_deviation > 0.3:
                condition_score += 0.4
                reasons.append(f"PCR extreme ({regime.pcr:.2f})")
            elif pcr_deviation > 0.2:
                condition_score += 0.2
                reasons.append(f"PCR moderate ({regime.pcr:.2f})")
            
            if regime.day_type != 'EXPIRY':
                condition_score += 0.1
                reasons.append("Non-expiry good for directional")
                
        elif strategy_name == 'BuyCallScalp':
            # Scalping works best in trends/volatility
            if regime.regime_type in ['TRENDING', 'VOLATILE']:
                condition_score += 0.4
                reasons.append(f"{regime.regime_type} market good for scalps")
            
            if regime.vix_level > 12:
                condition_score += 0.2
                reasons.append("VIX supports momentum")
                
            if 0.005 < regime.intraday_range_pct < 0.02:
                condition_score += 0.2
                reasons.append("Healthy movement range")
        
        final_score = base_score * 0.4 + condition_score * 0.6
        
        return StrategyScore(
            strategy_name=strategy_name,
            base_score=base_score,
            condition_score=condition_score,
            final_score=round(final_score, 3),
            reasons=reasons
        )
    
    def select_best_strategy(self, data_slice, params: Dict = None) -> Tuple[str, Optional[Dict]]:
        """
        Select the best strategy and generate signal.
        
        Returns:
            Tuple of (strategy_name, signal_dict or None)
        """
        params = params or {}
        
        if len(data_slice) < 20:
            return 'NONE', None
        
        current_time = data_slice.iloc[-1]['datetime']
        
        # Check signal gap
        if self.last_signal_time:
            gap = (current_time - self.last_signal_time).total_seconds() / 60
            if gap < self.min_signal_gap_minutes:
                return 'COOLDOWN', None
        
        # Classify market regime
        regime = self.classify_regime(data_slice, current_time)
        self.current_regime = regime
        
        # Score all strategies
        theta_score = self.score_strategy('ThetaDecay', regime)
        orb_score = self.score_strategy('ORB', regime)
        oi_score = self.score_strategy('OIDirectional', regime)
        scalp_score = self.score_strategy('BuyCallScalp', regime)
        
        scores = [theta_score, orb_score, oi_score, scalp_score]
        
        # Sort by final score
        scores.sort(key=lambda x: x.final_score, reverse=True)
        
        # Try each strategy in order of score
        for score in scores:
            if score.final_score < 0.3:  # Minimum threshold
                continue
            
            signal = None
            
            if score.strategy_name == 'ThetaDecay':
                signal = self.theta_strategy.generate_signal(data_slice, params)
            elif score.strategy_name == 'ORB':
                signal = self.orb_strategy.generate_signal(data_slice, params)
            elif score.strategy_name == 'OIDirectional':
                signal = self.oi_strategy.generate_signal(data_slice, params)
            elif score.strategy_name == 'BuyCallScalp':
                signal = self.buy_call_strategy.generate_signal(data_slice, params)
            
            if signal:
                # Add strategy selector metadata
                signal['selected_by'] = 'StrategySelector'
                signal['regime'] = regime.regime_type
                signal['strategy_score'] = score.final_score
                signal['selection_reasons'] = score.reasons
                
                self.last_signal_time = current_time
                
                self.logger.info(
                    f"Selected {score.strategy_name} (score: {score.final_score:.2f}) "
                    f"in {regime.regime_type} regime"
                )
                
                return score.strategy_name, signal
        
        return 'NO_SIGNAL', None
    
    def update_performance(self, strategy_name: str, pnl: float, is_win: bool):
        """Update strategy performance tracking."""
        if strategy_name in self.strategy_performance:
            self.strategy_performance[strategy_name]['pnl'] += pnl
            if is_win:
                self.strategy_performance[strategy_name]['wins'] += 1
            else:
                self.strategy_performance[strategy_name]['losses'] += 1
            
            # Update base scores based on recent performance
            perf = self.strategy_performance[strategy_name]
            total = perf['wins'] + perf['losses']
            if total >= 10:  # Minimum trades for adjustment
                recent_win_rate = perf['wins'] / total
                # Blend historical and recent
                self.base_scores[strategy_name] = (
                    self.base_scores[strategy_name] * 0.7 +
                    recent_win_rate * 0.3
                )
    
    def _print_performance_summary(self):
        """Print performance summary of all strategies."""
        self.logger.info("="*50)
        self.logger.info("STRATEGY SELECTOR PERFORMANCE SUMMARY")
        self.logger.info("="*50)
        
        for name, perf in self.strategy_performance.items():
            total = perf['wins'] + perf['losses']
            win_rate = perf['wins'] / total * 100 if total > 0 else 0
            self.logger.info(
                f"{name}: {perf['wins']}W / {perf['losses']}L "
                f"({win_rate:.1f}%) | P&L: ₹{perf['pnl']:,.0f}"
            )
        
        self.logger.info("="*50)
    
    def get_status(self) -> Dict:
        """Get current strategy selector status."""
        return {
            'current_regime': self.current_regime.regime_type if self.current_regime else 'UNKNOWN',
            'vix': self.current_vix,
            'pcr': self.current_pcr,
            'strategies': list(self.strategy_performance.keys()),
            'performance': self.strategy_performance,
            'base_scores': self.base_scores
        }


def multi_strategy_selector_func(data_slice, params: Dict = None) -> Optional[Dict]:
    """Standalone function for backtest engine using global selector."""
    strategy_name, signal = strategy_selector.select_best_strategy(data_slice, params)
    return signal


# Global instance
strategy_selector = StrategySelector()

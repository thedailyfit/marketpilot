"""
Enhanced Scalping Strategy
Uses multi-indicator confirmation: RSI + EMA Trend + Volume + VWAP
"""
import time
from typing import Optional, List
from core.data_models import Tick, Candle, Signal
from agents.trading.strategies.base_strategy import BaseStrategy
from core.indicators import (
    rsi, ema_current, vwap, volume_ratio, 
    trend_direction, market_regime, atr
)


class ScalpingStrategy(BaseStrategy):
    """
    Enhanced Scalping Strategy with Multi-Indicator Confirmation.
    
    Buy Conditions (ALL must be true):
    - RSI < 35 (oversold)
    - EMA Fast > EMA Slow (uptrend)
    - Volume > 1.2x average (strength)
    - Price > VWAP (bullish)
    - Market not in strong downtrend
    
    Sell Conditions (ALL must be true):
    - RSI > 65 (overbought)
    - EMA Fast < EMA Slow (downtrend)
    - Volume > 1.2x average (strength)
    - Price < VWAP (bearish)
    - Market not in strong uptrend
    """
    
    def __init__(self):
        super().__init__("ScalpingStrategy")
        
        # Indicator Parameters
        self.rsi_period = 14
        self.rsi_oversold = 35
        self.rsi_overbought = 65
        self.ema_fast_period = 9
        self.ema_slow_period = 21
        self.volume_threshold = 1.2
        
        # State
        self.price_history: List[float] = []
        self.candle_history: List[dict] = []
        self.last_signal_time = 0.0
        self.min_signal_interval = 60.0  # Minimum 60 seconds between signals
        
    def on_tick(self, tick: Tick) -> Optional[Signal]:
        """Process incoming tick (not used for signal generation)."""
        self.price_history.append(tick.ltp)
        self.price_history = self.price_history[-200:]  # Keep last 200 prices
        return None

    def on_candle(self, candle: Candle) -> Optional[Signal]:
        """Store candle data for indicators."""
        candle_dict = {
            'open': candle.open if hasattr(candle, 'open') else candle.get('open', 0),
            'high': candle.high if hasattr(candle, 'high') else candle.get('high', 0),
            'low': candle.low if hasattr(candle, 'low') else candle.get('low', 0),
            'close': candle.close if hasattr(candle, 'close') else candle.get('close', 0),
            'volume': candle.volume if hasattr(candle, 'volume') else candle.get('volume', 0),
        }
        self.candle_history.append(candle_dict)
        self.candle_history = self.candle_history[-100:]  # Keep last 100 candles
        return None

    def on_features(self, features: dict) -> Optional[Signal]:
        """
        Core signal generation with multi-indicator confirmation.
        """
        current_time = time.time()
        
        # Rate limit signals
        if current_time - self.last_signal_time < self.min_signal_interval:
            return None
        
        sym = features.get("symbol", "UNKNOWN")
        current_price = features.get("ltp", 0.0)
        current_volume = features.get("volume", 0)
        
        # Add current price to history
        if current_price > 0:
            self.price_history.append(current_price)
            self.price_history = self.price_history[-200:]
        
        # Need minimum data
        if len(self.price_history) < 30:
            return None
        
        # === CALCULATE INDICATORS ===
        
        # 1. RSI
        rsi_value = features.get("rsi_14", rsi(self.price_history, self.rsi_period))
        
        # 2. Trend (EMA Crossover)
        trend = trend_direction(self.price_history, self.ema_fast_period, self.ema_slow_period)
        
        # 3. Volume Ratio
        vol_ratio = 1.0
        if self.candle_history:
            vol_ratio = volume_ratio(current_volume, self.candle_history)
        
        # 4. VWAP
        vwap_value = 0.0
        if self.candle_history:
            vwap_value = vwap(self.candle_history)
        
        # 5. Market Regime & ADX (TRAP DETECTOR)
        regime = "RANGING"
        adx_value = 0.0
        if self.candle_history:
            adx_value = adx(self.candle_history)
            
        if self.candle_history and len(self.price_history) > 20:
            regime = market_regime(self.candle_history, self.price_history)
        
        # === SIGNAL LOGIC ===
        
        signal = None
        
        # TRAP DETECTOR: Disable trading if ADX < 20 (Chop)
        # Exception: You can disable this if you want to trade range breakouts, 
        # but for "Option Buyer Protection", we enforce it.
        trend_strength_ok = adx_value > 20
        
        # BUY CONDITIONS
        buy_conditions = {
            "rsi_oversold": rsi_value < self.rsi_oversold,
            "trend_up": trend.direction == "UP" or trend.direction == "NEUTRAL",
            "volume_ok": vol_ratio >= self.volume_threshold or len(self.candle_history) < 10,
            "above_vwap": current_price > vwap_value or vwap_value == 0,
            "not_downtrend": regime != "TRENDING_DOWN",
            "trap_filter": trend_strength_ok
        }
        
        # SELL CONDITIONS  
        sell_conditions = {
            "rsi_overbought": rsi_value > self.rsi_overbought,
            "trend_down": trend.direction == "DOWN" or trend.direction == "NEUTRAL",
            "volume_ok": vol_ratio >= self.volume_threshold or len(self.candle_history) < 10,
            "below_vwap": current_price < vwap_value or vwap_value == 0,
            "not_uptrend": regime != "TRENDING_UP",
            "trap_filter": trend_strength_ok
        }
        
        # Check BUY
        if all(buy_conditions.values()):
            signal = Signal(
                symbol=sym,
                signal_type="BUY",
                strength=0.8 + (trend.strength * 0.2),  # Stronger trend = stronger signal
                timestamp=current_time,
                reason=self._build_reason("BUY", rsi_value, trend, vol_ratio, regime),
                strategy_id=self.name,
                stop_loss=0.0,  # Will be calculated by RiskAgent
                target_price=0.0
            )
            self.last_signal_time = current_time
            
        # Check SELL
        elif all(sell_conditions.values()):
            signal = Signal(
                symbol=sym,
                signal_type="SELL",
                strength=0.8 + (trend.strength * 0.2),
                timestamp=current_time,
                reason=self._build_reason("SELL", rsi_value, trend, vol_ratio, regime),
                strategy_id=self.name,
                stop_loss=0.0,
                target_price=0.0
            )
            self.last_signal_time = current_time
        
        return signal
    
    def _build_reason(self, direction: str, rsi_val: float, trend, vol_ratio: float, regime: str) -> str:
        """Build human-readable reason for signal."""
        parts = []
        
        if direction == "BUY":
            parts.append(f"RSI Oversold ({rsi_val:.1f})")
        else:
            parts.append(f"RSI Overbought ({rsi_val:.1f})")
        
        parts.append(f"Trend: {trend.direction}")
        
        if vol_ratio >= self.volume_threshold:
            parts.append(f"Vol: {vol_ratio:.1f}x")
        
        parts.append(f"Regime: {regime}")
        
        return " | ".join(parts)
    
    def get_state(self) -> dict:
        """Get current strategy state for dashboard."""
        if len(self.price_history) < 20:
            return {"status": "warming_up", "data_points": len(self.price_history)}
        
        trend = trend_direction(self.price_history, self.ema_fast_period, self.ema_slow_period)
        regime = "RANGING"
        adx_value = 0.0
        
        if self.candle_history:
            adx_value = adx(self.candle_history)
            
        if self.candle_history and len(self.price_history) > 20:
            regime = market_regime(self.candle_history, self.price_history)
        
        return {
            "rsi": round(rsi(self.price_history, self.rsi_period), 2),
            "adx": round(adx_value, 2), # NEW
            "ema_fast": trend.ema_fast,
            "ema_slow": trend.ema_slow,
            "trend": trend.direction,
            "trend_strength": trend.strength,
            "regime": regime,
            "data_points": len(self.price_history)
        }

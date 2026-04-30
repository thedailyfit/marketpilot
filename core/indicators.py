"""
Technical Indicators Library
Provides EMA, VWAP, ATR, Volume Ratio, and Trend Detection.
"""
from typing import List, Optional
from dataclasses import dataclass

@dataclass 
class TrendState:
    direction: str  # "UP", "DOWN", "NEUTRAL"
    strength: float  # 0.0 to 1.0
    ema_fast: float
    ema_slow: float


def ema(prices: List[float], period: int) -> List[float]:
    """
    Calculate Exponential Moving Average.
    
    Args:
        prices: List of prices (close prices typically)
        period: EMA period
    
    Returns:
        List of EMA values (same length as prices, early values are SMA)
    """
    if not prices:
        return []
    
    if len(prices) < period:
        # Not enough data, return simple average repeated
        sma = sum(prices) / len(prices)
        return [sma] * len(prices)
    
    ema_values = []
    multiplier = 2 / (period + 1)
    
    # First value is SMA
    sma = sum(prices[:period]) / period
    ema_values.extend([sma] * period)
    
    # Calculate EMA for rest
    prev_ema = sma
    for price in prices[period:]:
        current_ema = (price * multiplier) + (prev_ema * (1 - multiplier))
        ema_values.append(current_ema)
        prev_ema = current_ema
    
    return ema_values


def ema_current(prices: List[float], period: int) -> float:
    """Get current (last) EMA value."""
    ema_list = ema(prices, period)
    return ema_list[-1] if ema_list else 0.0


def sma(prices: List[float], period: int) -> float:
    """Simple Moving Average of last N prices."""
    if len(prices) < period:
        return sum(prices) / len(prices) if prices else 0.0
    return sum(prices[-period:]) / period


def vwap(candles: List[dict]) -> float:
    """
    Calculate Volume Weighted Average Price.
    
    Args:
        candles: List of candle dicts with 'high', 'low', 'close', 'volume'
    
    Returns:
        VWAP value
    """
    if not candles:
        return 0.0
    
    cumulative_volume = 0.0
    cumulative_tp_volume = 0.0
    
    for candle in candles:
        # Typical Price = (High + Low + Close) / 3
        high = candle.get('high', 0)
        low = candle.get('low', 0)
        close = candle.get('close', 0)
        volume = candle.get('volume', 0)
        
        tp = (high + low + close) / 3
        cumulative_tp_volume += tp * volume
        cumulative_volume += volume
    
    if cumulative_volume == 0:
        return candles[-1].get('close', 0)
    
    return round(cumulative_tp_volume / cumulative_volume, 2)


def atr(candles: List[dict], period: int = 14) -> float:
    """
    Average True Range for volatility measurement.
    (Re-exported from risk_calculator for convenience)
    """
    from core.risk_calculator import calculate_atr
    return calculate_atr(candles, period)


def volume_ratio(current_volume: float, candles: List[dict], period: int = 20) -> float:
    """
    Calculate volume ratio vs average volume.
    
    Args:
        current_volume: Current candle/tick volume
        candles: Historical candles with 'volume'
        period: Lookback period for average
    
    Returns:
        Ratio (e.g., 1.5 = 50% above average)
    """
    if not candles:
        return 1.0
    
    volumes = [c.get('volume', 0) for c in candles[-period:]]
    avg_volume = sum(volumes) / len(volumes) if volumes else 1
    
    if avg_volume == 0:
        return 1.0
    
    return round(current_volume / avg_volume, 2)


def rsi(prices: List[float], period: int = 14) -> float:
    """
    Calculate Relative Strength Index.
    
    Args:
        prices: List of close prices
        period: RSI period (default 14)
    
    Returns:
        RSI value (0-100)
    """
    if len(prices) < period + 1:
        return 50.0  # Neutral if not enough data
    
    # Calculate price changes
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    # Split into gains and losses
    gains = [c if c > 0 else 0 for c in changes]
    losses = [abs(c) if c < 0 else 0 for c in changes]
    
    # First average (SMA)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Smooth with Wilder's smoothing for remaining
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi_value = 100 - (100 / (1 + rs))
    
    return round(rsi_value, 2)


def trend_direction(prices: List[float], fast_period: int = 9, slow_period: int = 21) -> TrendState:
    """
    Determine trend direction using EMA crossover.
    
    Args:
        prices: List of close prices
        fast_period: Fast EMA period
        slow_period: Slow EMA period
    
    Returns:
        TrendState with direction and strength
    """
    if len(prices) < slow_period:
        return TrendState("NEUTRAL", 0.0, 0.0, 0.0)
    
    ema_fast = ema_current(prices, fast_period)
    ema_slow = ema_current(prices, slow_period)
    
    # Calculate spread as percentage
    spread_percent = ((ema_fast - ema_slow) / ema_slow) * 100 if ema_slow != 0 else 0
    
    # Determine direction
    if spread_percent > 0.1:
        direction = "UP"
        strength = min(abs(spread_percent) / 2, 1.0)  # Normalize to 0-1
    elif spread_percent < -0.1:
        direction = "DOWN"
        strength = min(abs(spread_percent) / 2, 1.0)
    else:
        direction = "NEUTRAL"
        strength = 0.0
    
    return TrendState(
        direction=direction,
        strength=round(strength, 2),
        ema_fast=round(ema_fast, 2),
        ema_slow=round(ema_slow, 2)
    )


def adx(candles: List[dict], period: int = 14) -> float:
    """
    Average Directional Index for trend strength.
    
    Returns:
        ADX value (0-100). > 25 indicates trending market.
    """
    if len(candles) < period + 1:
        return 20.0  # Default non-trending
    
    # Calculate +DM and -DM
    plus_dm = []
    minus_dm = []
    tr_list = []
    
    for i in range(1, len(candles)):
        high = candles[i]['high']
        low = candles[i]['low']
        prev_high = candles[i-1]['high']
        prev_low = candles[i-1]['low']
        prev_close = candles[i-1]['close']
        
        # True Range
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
        
        # Directional Movement
        up_move = high - prev_high
        down_move = prev_low - low
        
        if up_move > down_move and up_move > 0:
            plus_dm.append(up_move)
        else:
            plus_dm.append(0)
        
        if down_move > up_move and down_move > 0:
            minus_dm.append(down_move)
        else:
            minus_dm.append(0)
    
    # Smooth with Wilder's method
    def wilder_smooth(values, period):
        if len(values) < period:
            return sum(values) / len(values) if values else 0
        result = sum(values[:period])
        for v in values[period:]:
            result = result - (result / period) + v
        return result / period
    
    atr_val = wilder_smooth(tr_list, period)
    plus_di_final = (wilder_smooth(plus_dm, period) / atr_val * 100) if atr_val > 0 else 0
    minus_di_final = (wilder_smooth(minus_dm, period) / atr_val * 100) if atr_val > 0 else 0
    
    # To calculate proper ADX, we need the SEQUENCE of DX values, not just the last one.
    # We will compute DX for each step after the initial period.
    
    # 1. Initialize Smoothed Values
    smooth_tr = sum(tr_list[:period])
    smooth_plus = sum(plus_dm[:period])
    smooth_minus = sum(minus_dm[:period])
    
    dx_values = []
    
    # 2. Loop through history to build DX chain
    for i in range(period, len(tr_list)):
        current_tr = tr_list[i]
        current_plus = plus_dm[i]
        current_minus = minus_dm[i]
        
        # Wilder Smoothing: Prev - (Prev/N) + Current
        smooth_tr = smooth_tr - (smooth_tr / period) + current_tr
        smooth_plus = smooth_plus - (smooth_plus / period) + current_plus
        smooth_minus = smooth_minus - (smooth_minus / period) + current_minus
        
        # Calculate DIs
        p_di = (smooth_plus / smooth_tr * 100) if smooth_tr > 0 else 0
        m_di = (smooth_minus / smooth_tr * 100) if smooth_tr > 0 else 0
        
        # Calculate DX
        div = p_di + m_di
        dx = (abs(p_di - m_di) / div * 100) if div > 0 else 0
        dx_values.append(dx)
        
    if not dx_values:
        return 20.0
        
    # 3. Calculate ADX (Smoothed DX)
    # First ADX is average of first 'period' DX values
    if len(dx_values) < period:
        return sum(dx_values) / len(dx_values)
        
    adx_val = sum(dx_values[:period]) / period
    for i in range(period, len(dx_values)):
        adx_val = ((adx_val * (period - 1)) + dx_values[i]) / period
        
    return round(adx_val, 2)


def is_trending(candles: List[dict], threshold: float = 25.0) -> bool:
    """Check if market is trending based on ADX."""
    return adx(candles) > threshold


def market_regime(candles: List[dict], prices: List[float]) -> str:
    """
    Detect market regime.
    
    Returns:
        "TRENDING_UP", "TRENDING_DOWN", or "RANGING"
    """
    if not candles or not prices:
        return "RANGING"
    
    # Use ADX for trending detection
    adx_value = adx(candles)
    trend = trend_direction(prices)
    
    if adx_value > 25:
        if trend.direction == "UP":
            return "TRENDING_UP"
        elif trend.direction == "DOWN":
            return "TRENDING_DOWN"
    
    return "RANGING"

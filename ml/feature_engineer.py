"""
ML Feature Engineer
Extracts features from market data for prediction model.
"""
from typing import List, Dict, Optional
from datetime import datetime
from core.indicators import rsi, ema_current, vwap, volume_ratio, atr, adx, trend_direction


def extract_features(
    candles: List[dict],
    prices: List[float],
    current_volume: float = 0.0,
    timestamp: float = 0.0
) -> Dict[str, float]:
    """
    Extract features for ML model prediction.
    
    Args:
        candles: Historical OHLCV candles
        prices: Price history (close prices)
        current_volume: Current tick/candle volume
        timestamp: Current timestamp
    
    Returns:
        Dict of feature name -> value
    """
    features = {}
    
    # === PRICE-BASED FEATURES ===
    
    # RSI
    features['rsi_14'] = rsi(prices, 14) if len(prices) >= 15 else 50.0
    features['rsi_7'] = rsi(prices, 7) if len(prices) >= 8 else 50.0
    
    # RSI Change (momentum)
    if len(prices) >= 20:
        rsi_now = rsi(prices, 14)
        rsi_prev = rsi(prices[:-5], 14)
        features['rsi_change'] = rsi_now - rsi_prev
    else:
        features['rsi_change'] = 0.0
    
    # === TREND FEATURES ===
    
    # EMA values
    features['ema_9'] = ema_current(prices, 9) if len(prices) >= 9 else prices[-1] if prices else 0
    features['ema_21'] = ema_current(prices, 21) if len(prices) >= 21 else prices[-1] if prices else 0
    
    # EMA spread (trend strength)
    if features['ema_21'] > 0:
        features['ema_spread'] = ((features['ema_9'] - features['ema_21']) / features['ema_21']) * 100
    else:
        features['ema_spread'] = 0.0
    
    # Trend direction
    trend = trend_direction(prices, 9, 21)
    features['trend_up'] = 1.0 if trend.direction == "UP" else 0.0
    features['trend_down'] = 1.0 if trend.direction == "DOWN" else 0.0
    features['trend_strength'] = trend.strength
    
    # === VOLATILITY FEATURES ===
    
    # ATR
    features['atr'] = atr(candles, 14) if len(candles) >= 15 else 50.0
    
    # ATR percentage of price
    current_price = prices[-1] if prices else 19500.0
    features['atr_percent'] = (features['atr'] / current_price) * 100 if current_price > 0 else 0.0
    
    # Price range (high-low of recent candles)
    if candles:
        recent = candles[-5:]
        high = max(c.get('high', 0) for c in recent)
        low = min(c.get('low', float('inf')) for c in recent)
        features['price_range'] = high - low
    else:
        features['price_range'] = 0.0
    
    # === VOLUME FEATURES ===
    
    # Volume ratio
    features['volume_ratio'] = volume_ratio(current_volume, candles) if candles else 1.0
    
    # Volume trend (is volume increasing?)
    if len(candles) >= 10:
        recent_vol = sum(c.get('volume', 0) for c in candles[-5:]) / 5
        older_vol = sum(c.get('volume', 0) for c in candles[-10:-5]) / 5
        features['volume_trend'] = (recent_vol / older_vol) if older_vol > 0 else 1.0
    else:
        features['volume_trend'] = 1.0
    
    # === VWAP FEATURES ===
    
    vwap_value = vwap(candles) if candles else current_price
    features['vwap'] = vwap_value
    features['price_vs_vwap'] = ((current_price - vwap_value) / vwap_value) * 100 if vwap_value > 0 else 0.0
    
    # === ADX (Trend Strength) ===
    
    features['adx'] = adx(candles, 14) if len(candles) >= 15 else 20.0
    features['is_trending'] = 1.0 if features['adx'] > 25 else 0.0
    
    # === TIME FEATURES ===
    
    if timestamp > 0:
        dt = datetime.fromtimestamp(timestamp)
    else:
        dt = datetime.now()
    
    # Hour of day (important for intraday trading)
    features['hour'] = float(dt.hour)
    features['minute'] = float(dt.minute)
    
    # Time slots (encoded)
    features['is_morning'] = 1.0 if 9 <= dt.hour < 11 else 0.0
    features['is_midday'] = 1.0 if 11 <= dt.hour < 14 else 0.0
    features['is_afternoon'] = 1.0 if 14 <= dt.hour < 16 else 0.0
    
    # Day of week
    features['day_of_week'] = float(dt.weekday())  # 0=Monday, 4=Friday
    features['is_friday'] = 1.0 if dt.weekday() == 4 else 0.0
    
    # === PRICE MOMENTUM ===
    
    # Price change over last N periods
    if len(prices) >= 5:
        features['price_change_5'] = ((prices[-1] - prices[-5]) / prices[-5]) * 100
    else:
        features['price_change_5'] = 0.0
    
    if len(prices) >= 10:
        features['price_change_10'] = ((prices[-1] - prices[-10]) / prices[-10]) * 100
    else:
        features['price_change_10'] = 0.0
    
    return features


def get_feature_names() -> List[str]:
    """Get list of feature names for model training."""
    return [
        'rsi_14', 'rsi_7', 'rsi_change',
        'ema_9', 'ema_21', 'ema_spread',
        'trend_up', 'trend_down', 'trend_strength',
        'atr', 'atr_percent', 'price_range',
        'volume_ratio', 'volume_trend',
        'vwap', 'price_vs_vwap',
        'adx', 'is_trending',
        'hour', 'minute',
        'is_morning', 'is_midday', 'is_afternoon',
        'day_of_week', 'is_friday',
        'price_change_5', 'price_change_10'
    ]


def features_to_array(features: Dict[str, float]) -> List[float]:
    """Convert feature dict to array for model input."""
    names = get_feature_names()
    return [features.get(name, 0.0) for name in names]

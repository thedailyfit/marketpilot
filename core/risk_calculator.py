"""
Risk Calculator Module
Provides ATR-based stop-loss, take-profit, and position sizing calculations.
"""
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class RiskLevels:
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: int
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float


def calculate_atr(candles: List[dict], period: int = 14) -> float:
    """
    Calculate Average True Range (ATR) for volatility-based stops.
    
    Args:
        candles: List of candle dicts with 'high', 'low', 'close' keys
        period: ATR period (default 14)
    
    Returns:
        ATR value
    """
    if len(candles) < period + 1:
        # Not enough data, return default volatility estimate
        if candles:
            avg_range = sum(c['high'] - c['low'] for c in candles) / len(candles)
            return avg_range
        return 50.0  # Default for NIFTY-like instruments
    
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i]['high']
        low = candles[i]['low']
        prev_close = candles[i-1]['close']
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    # Simple Moving Average of True Range (last 'period' values)
    recent_tr = true_ranges[-period:]
    atr = sum(recent_tr) / len(recent_tr)
    
    return round(atr, 2)


def calculate_stop_loss(
    entry_price: float,
    atr: float,
    direction: str = "BUY",
    multiplier: float = 1.5
) -> float:
    """
    Calculate stop-loss based on ATR.
    
    Args:
        entry_price: Entry price of the trade
        atr: Current ATR value
        direction: 'BUY' or 'SELL'
        multiplier: ATR multiplier (1.5 = conservative, 2.0 = wider)
    
    Returns:
        Stop-loss price
    """
    stop_distance = atr * multiplier
    
    if direction == "BUY":
        return round(entry_price - stop_distance, 2)
    else:  # SELL
        return round(entry_price + stop_distance, 2)


def calculate_take_profit(
    entry_price: float,
    stop_loss: float,
    direction: str = "BUY",
    rr_ratio: float = 2.0
) -> float:
    """
    Calculate take-profit based on risk-reward ratio.
    
    Args:
        entry_price: Entry price
        stop_loss: Stop-loss price
        direction: 'BUY' or 'SELL'
        rr_ratio: Risk-reward ratio (default 2:1)
    
    Returns:
        Take-profit price
    """
    risk = abs(entry_price - stop_loss)
    reward = risk * rr_ratio
    
    if direction == "BUY":
        return round(entry_price + reward, 2)
    else:  # SELL
        return round(entry_price - reward, 2)


def calculate_position_size(
    account_balance: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float,
    lot_size: int = 1
) -> int:
    """
    Calculate position size based on risk percentage.
    
    Args:
        account_balance: Total account balance
        risk_percent: Max risk per trade (e.g., 1.0 = 1%)
        entry_price: Entry price
        stop_loss: Stop-loss price
        lot_size: Minimum lot size (for F&O)
    
    Returns:
        Number of lots/shares to buy
    """
    # Max amount to risk
    max_risk_amount = account_balance * (risk_percent / 100)
    
    # Risk per unit
    stop_distance = abs(entry_price - stop_loss)
    if stop_distance == 0:
        return lot_size  # Minimum
    
    # Calculate quantity
    raw_qty = max_risk_amount / stop_distance
    
    # Round to lot size
    position_size = max(lot_size, int(raw_qty // lot_size) * lot_size)
    
    return position_size


def calculate_risk_levels(
    entry_price: float,
    candles: List[dict],
    direction: str = "BUY",
    account_balance: float = 100000.0,
    risk_percent: float = 1.0,
    atr_multiplier: float = 1.5,
    rr_ratio: float = 2.0,
    lot_size: int = 1
) -> RiskLevels:
    """
    Calculate complete risk levels for a trade.
    
    Returns:
        RiskLevels dataclass with SL, TP, position size, etc.
    """
    atr = calculate_atr(candles)
    stop_loss = calculate_stop_loss(entry_price, atr, direction, atr_multiplier)
    take_profit = calculate_take_profit(entry_price, stop_loss, direction, rr_ratio)
    position_size = calculate_position_size(
        account_balance, risk_percent, entry_price, stop_loss, lot_size
    )
    
    risk_amount = abs(entry_price - stop_loss) * position_size
    reward_amount = abs(take_profit - entry_price) * position_size
    
    return RiskLevels(
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=position_size,
        risk_amount=round(risk_amount, 2),
        reward_amount=round(reward_amount, 2),
        risk_reward_ratio=rr_ratio
    )


def calculate_trailing_stop(
    current_price: float,
    entry_price: float,
    current_stop: float,
    atr: float,
    direction: str = "BUY",
    trail_multiplier: float = 1.0
) -> float:
    """
    Calculate trailing stop based on price movement.
    Only moves stop in profitable direction.
    
    Args:
        current_price: Current market price
        entry_price: Original entry price
        current_stop: Current stop-loss level
        atr: Current ATR value
        direction: 'BUY' or 'SELL'
        trail_multiplier: ATR multiplier for trail distance
    
    Returns:
        New stop-loss price (only if improved)
    """
    trail_distance = atr * trail_multiplier
    
    if direction == "BUY":
        # For long positions, trail stop upward
        new_stop = current_price - trail_distance
        if new_stop > current_stop and current_price > entry_price:
            return round(new_stop, 2)
    else:  # SELL
        # For short positions, trail stop downward
        new_stop = current_price + trail_distance
        if new_stop < current_stop and current_price < entry_price:
            return round(new_stop, 2)
    
    return current_stop  # No change

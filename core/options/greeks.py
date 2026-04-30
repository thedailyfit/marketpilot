"""
Greeks Calculator
Black-Scholes pricing and Greeks calculation for Indian index options.
"""
import math
from dataclasses import dataclass
from typing import Optional
from scipy.stats import norm
from scipy.optimize import brentq


@dataclass
class Greeks:
    """Option Greeks."""
    delta: float
    gamma: float
    theta: float  # Daily
    vega: float
    rho: float


def black_scholes_price(
    spot: float,
    strike: float,
    time_to_expiry: float,  # In years
    volatility: float,      # Annualized (e.g., 0.20 for 20%)
    risk_free_rate: float,  # Annualized (e.g., 0.07 for 7%)
    option_type: str        # 'CE' or 'PE'
) -> float:
    """
    Calculate Black-Scholes option price.
    
    Args:
        spot: Current spot price
        strike: Strike price
        time_to_expiry: Time to expiry in years (e.g., 7/365 for 7 days)
        volatility: Annualized IV (e.g., 0.15 for 15%)
        risk_free_rate: Risk-free rate (e.g., 0.07 for 7%)
        option_type: 'CE' for Call, 'PE' for Put
    
    Returns:
        Option premium
    """
    if time_to_expiry <= 0:
        # At expiry
        if option_type == 'CE':
            return max(0, spot - strike)
        else:
            return max(0, strike - spot)
    
    if volatility <= 0:
        volatility = 0.001  # Minimum vol
    
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * math.sqrt(time_to_expiry))
    d2 = d1 - volatility * math.sqrt(time_to_expiry)
    
    if option_type == 'CE':
        price = spot * norm.cdf(d1) - strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
    else:
        price = strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) - spot * norm.cdf(-d1)
    
    return max(0, price)


def calculate_greeks(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
    option_type: str
) -> Greeks:
    """
    Calculate all Greeks for an option.
    
    Returns:
        Greeks dataclass with delta, gamma, theta (daily), vega, rho
    """
    if time_to_expiry <= 0:
        # At expiry, greeks are zero except delta
        if option_type == 'CE':
            delta = 1.0 if spot > strike else 0.0
        else:
            delta = -1.0 if spot < strike else 0.0
        return Greeks(delta=delta, gamma=0, theta=0, vega=0, rho=0)
    
    if volatility <= 0:
        volatility = 0.001
    
    sqrt_t = math.sqrt(time_to_expiry)
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    
    # Delta
    if option_type == 'CE':
        delta = norm.cdf(d1)
    else:
        delta = norm.cdf(d1) - 1
    
    # Gamma (same for call and put)
    gamma = norm.pdf(d1) / (spot * volatility * sqrt_t)
    
    # Theta (daily, not annualized)
    if option_type == 'CE':
        theta = (
            -(spot * norm.pdf(d1) * volatility) / (2 * sqrt_t)
            - risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
        ) / 365  # Convert to daily
    else:
        theta = (
            -(spot * norm.pdf(d1) * volatility) / (2 * sqrt_t)
            + risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2)
        ) / 365
    
    # Vega (per 1% vol change)
    vega = spot * sqrt_t * norm.pdf(d1) / 100
    
    # Rho
    if option_type == 'CE':
        rho = strike * time_to_expiry * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2) / 100
    else:
        rho = -strike * time_to_expiry * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) / 100
    
    return Greeks(
        delta=round(delta, 4),
        gamma=round(gamma, 6),
        theta=round(theta, 2),
        vega=round(vega, 2),
        rho=round(rho, 2)
    )


def implied_volatility(
    option_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    option_type: str,
    precision: float = 0.0001
) -> Optional[float]:
    """
    Calculate implied volatility using Brent's method.
    
    Returns:
        IV as decimal (e.g., 0.20 for 20%), or None if not found
    """
    if time_to_expiry <= 0:
        return None
    
    # Intrinsic value check
    if option_type == 'CE':
        intrinsic = max(0, spot - strike)
    else:
        intrinsic = max(0, strike - spot)
    
    if option_price < intrinsic:
        return None  # Invalid price
    
    def objective(vol):
        return black_scholes_price(spot, strike, time_to_expiry, vol, risk_free_rate, option_type) - option_price
    
    try:
        # Search between 1% and 500% IV
        iv = brentq(objective, 0.01, 5.0, xtol=precision)
        return round(iv, 4)
    except ValueError:
        return None


def moneyness(spot: float, strike: float, option_type: str) -> str:
    """
    Determine if option is ITM, ATM, or OTM.
    """
    pct_diff = abs(spot - strike) / spot * 100
    
    if pct_diff < 0.5:
        return "ATM"
    
    if option_type == 'CE':
        if spot > strike:
            return "ITM"
        else:
            return "OTM"
    else:  # PE
        if spot < strike:
            return "ITM"
        else:
            return "OTM"


def days_to_years(days: int) -> float:
    """Convert days to years for Black-Scholes."""
    return days / 365.0

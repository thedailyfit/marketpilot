"""
Regime Constraints
Enforces trading restrictions based on market regime.
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class Regime(Enum):
    """Market regime types."""
    NORMAL = "NORMAL"
    TREND = "TREND"
    CHOP = "CHOP"
    TRAP = "TRAP"
    PANIC = "PANIC"
    UNKNOWN = "UNKNOWN"


@dataclass
class RegimeConfig:
    """Configuration for a specific regime."""
    max_position_pct: float      # Max position size as % of normal
    max_trades_per_day: int      # Max trades allowed
    theta_limit_pct: float       # Theta limit as % of normal
    vega_limit_pct: float        # Vega limit as % of normal
    allowed_strategies: List[str] # Allowed strategy types
    
    def to_dict(self) -> dict:
        return {
            "max_position_pct": self.max_position_pct,
            "max_trades_per_day": self.max_trades_per_day,
            "theta_limit_pct": self.theta_limit_pct,
            "vega_limit_pct": self.vega_limit_pct,
            "allowed_strategies": self.allowed_strategies
        }


# Regime-specific configurations
REGIME_CONFIGS = {
    Regime.NORMAL: RegimeConfig(
        max_position_pct=100,
        max_trades_per_day=3,
        theta_limit_pct=100,
        vega_limit_pct=100,
        allowed_strategies=["BUY_CALL", "BUY_PUT", "SELL_CALL", "SELL_PUT", "SPREAD", "STRADDLE", "STRANGLE"]
    ),
    Regime.TREND: RegimeConfig(
        max_position_pct=100,
        max_trades_per_day=3,
        theta_limit_pct=100,
        vega_limit_pct=100,
        allowed_strategies=["BUY_CALL", "BUY_PUT", "SELL_CALL", "SELL_PUT", "SPREAD"]
    ),
    Regime.CHOP: RegimeConfig(
        max_position_pct=75,
        max_trades_per_day=2,
        theta_limit_pct=80,
        vega_limit_pct=75,
        allowed_strategies=["SELL_CALL", "SELL_PUT", "STRADDLE", "STRANGLE", "IRON_CONDOR"]
    ),
    Regime.TRAP: RegimeConfig(
        max_position_pct=50,
        max_trades_per_day=1,
        theta_limit_pct=60,
        vega_limit_pct=50,
        allowed_strategies=["BUY_PUT", "SELL_CALL", "BEAR_SPREAD"]
    ),
    Regime.PANIC: RegimeConfig(
        max_position_pct=25,
        max_trades_per_day=1,
        theta_limit_pct=40,
        vega_limit_pct=25,
        allowed_strategies=["BUY_PUT", "BEAR_SPREAD"]  # Only downside protection
    ),
    Regime.UNKNOWN: RegimeConfig(
        max_position_pct=50,
        max_trades_per_day=1,
        theta_limit_pct=50,
        vega_limit_pct=50,
        allowed_strategies=["BUY_PUT"]  # Conservative until regime known
    )
}


class RegimeConstraints:
    """
    Enforces trading restrictions based on market regime.
    
    In PANIC mode:
    - Reduce position size to 25%
    - Allow only 1 trade per day
    - Restrict to downside strategies only
    - Slash theta/vega budgets
    
    This ensures capital protection during extreme volatility.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("RegimeConstraints")
        self.current_regime = Regime.UNKNOWN
        self.override_regime = None  # Manual override
        
    def update_regime(self, regime_str: str):
        """
        Update current regime from RegimeClassifier.
        
        Args:
            regime_str: Regime name (NORMAL, TREND, CHOP, TRAP, PANIC)
        """
        try:
            new_regime = Regime(regime_str.upper())
            if new_regime != self.current_regime:
                self.logger.info(f"🔄 Regime change: {self.current_regime.value} → {new_regime.value}")
                self.current_regime = new_regime
        except ValueError:
            self.logger.warning(f"Unknown regime: {regime_str}, using UNKNOWN")
            self.current_regime = Regime.UNKNOWN
    
    def set_override(self, regime_str: str, reason: str = ""):
        """
        Manually override regime detection.
        
        Args:
            regime_str: Regime to force
            reason: Why overriding
        """
        try:
            self.override_regime = Regime(regime_str.upper())
            self.logger.warning(f"⚠️ REGIME OVERRIDE: {self.override_regime.value} - {reason}")
        except ValueError:
            self.logger.error(f"Invalid override regime: {regime_str}")
    
    def clear_override(self):
        """Clear manual override."""
        self.override_regime = None
        self.logger.info("Override cleared, using detected regime")
    
    def get_active_regime(self) -> Regime:
        """Get the active regime (override or detected)."""
        return self.override_regime or self.current_regime
    
    def get_config(self) -> RegimeConfig:
        """Get configuration for active regime."""
        regime = self.get_active_regime()
        return REGIME_CONFIGS.get(regime, REGIME_CONFIGS[Regime.UNKNOWN])
    
    def check(self, strategy: str = None) -> Dict[str, any]:
        """
        Check regime constraints for trading.
        
        Args:
            strategy: Optional strategy type to validate
        
        Returns:
            Dict with allowed, constraints, and modifiers
        """
        config = self.get_config()
        regime = self.get_active_regime()
        
        result = {
            "allowed": True,
            "regime": regime.value,
            "size_modifier": config.max_position_pct / 100,
            "max_trades": config.max_trades_per_day,
            "theta_modifier": config.theta_limit_pct / 100,
            "vega_modifier": config.vega_limit_pct / 100,
            "allowed_strategies": config.allowed_strategies
        }
        
        # Check strategy if provided
        if strategy:
            strategy_upper = strategy.upper()
            if strategy_upper not in config.allowed_strategies:
                result["allowed"] = False
                result["reason"] = f"REGIME_BLOCK: {strategy} not allowed in {regime.value} mode"
                result["allowed_strategies"] = config.allowed_strategies
        
        # Add warnings for restrictive regimes
        if regime == Regime.PANIC:
            result["warning"] = "PANIC MODE: Downside strategies only, size at 25%"
        elif regime == Regime.TRAP:
            result["warning"] = "TRAP MODE: Conservative strategies only, size at 50%"
        elif regime == Regime.CHOP:
            result["warning"] = "CHOP MODE: Reduced size at 75%"
        
        return result
    
    def get_size_modifier(self) -> float:
        """Get position size modifier for current regime."""
        config = self.get_config()
        return config.max_position_pct / 100
    
    def get_max_trades(self) -> int:
        """Get max trades per day for current regime."""
        config = self.get_config()
        return config.max_trades_per_day
    
    def is_strategy_allowed(self, strategy: str) -> bool:
        """Check if a strategy is allowed in current regime."""
        config = self.get_config()
        return strategy.upper() in config.allowed_strategies
    
    def get_status(self) -> dict:
        """Get current regime constraint status."""
        config = self.get_config()
        regime = self.get_active_regime()
        
        return {
            "regime": regime.value,
            "is_override": self.override_regime is not None,
            "detected_regime": self.current_regime.value,
            "constraints": config.to_dict()
        }


# Singleton
regime_constraints = RegimeConstraints()

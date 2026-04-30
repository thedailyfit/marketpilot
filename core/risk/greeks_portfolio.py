"""
Greeks Portfolio Tracker
Tracks aggregate Greeks across all options positions.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class Position:
    """Single options position."""
    symbol: str
    strike: float
    expiry: str
    option_type: str  # CE, PE
    quantity: int     # Positive = long, negative = short
    entry_price: float
    current_price: float
    
    # Greeks
    delta: float
    gamma: float
    theta: float
    vega: float
    
    # P&L
    unrealized_pnl: float = 0.0
    
    def update_pnl(self):
        self.unrealized_pnl = (self.current_price - self.entry_price) * self.quantity


@dataclass
class PortfolioGreeks:
    """Aggregate Greeks for entire portfolio."""
    total_delta: float
    total_gamma: float
    total_theta: float   # Daily theta burn
    total_vega: float
    
    position_count: int
    long_count: int
    short_count: int
    
    margin_used: float
    max_loss: float
    
    # Exposure analysis
    delta_exposure_pct: float  # Delta as % of capital
    theta_burn_pct: float      # Daily theta as % of capital
    vega_exposure_pct: float   # Vega as % of capital
    
    def to_dict(self) -> dict:
        return {
            "delta": round(self.total_delta, 2),
            "gamma": round(self.total_gamma, 4),
            "theta": round(self.total_theta, 2),
            "vega": round(self.total_vega, 2),
            "positions": self.position_count,
            "long": self.long_count,
            "short": self.short_count,
            "max_loss": round(self.max_loss, 2),
            "delta_exposure_pct": round(self.delta_exposure_pct, 2),
            "theta_burn_pct": round(self.theta_burn_pct, 2),
            "vega_exposure_pct": round(self.vega_exposure_pct, 2)
        }


class GreeksPortfolioTracker:
    """
    Tracks and manages aggregate Greeks across all positions.
    
    Features:
    - Real-time portfolio Greeks calculation
    - Delta neutrality monitoring
    - Theta burn tracking
    - Vega exposure monitoring
    - Position-level breakdown
    """
    
    def __init__(self, capital: float = 500000):
        self.logger = logging.getLogger("GreeksPortfolioTracker")
        self.capital = capital
        self.positions: Dict[str, Position] = {}  # position_id -> Position
        
        # Current aggregate
        self.current_greeks: Optional[PortfolioGreeks] = None
    
    def add_position(
        self,
        position_id: str,
        position: Position
    ):
        """Add or update a position."""
        self.positions[position_id] = position
        self._recalculate()
        self.logger.info(f"Added position: {position_id}")
    
    def remove_position(self, position_id: str):
        """Remove a position."""
        if position_id in self.positions:
            del self.positions[position_id]
            self._recalculate()
            self.logger.info(f"Removed position: {position_id}")
    
    def update_position_greeks(
        self,
        position_id: str,
        delta: float,
        gamma: float,
        theta: float,
        vega: float,
        current_price: float
    ):
        """Update Greeks for existing position."""
        if position_id in self.positions:
            pos = self.positions[position_id]
            pos.delta = delta
            pos.gamma = gamma
            pos.theta = theta
            pos.vega = vega
            pos.current_price = current_price
            pos.update_pnl()
            self._recalculate()
    
    def clear_all(self):
        """Clear all positions."""
        self.positions.clear()
        self.current_greeks = None
    
    def _recalculate(self):
        """Recalculate aggregate Greeks."""
        if not self.positions:
            self.current_greeks = None
            return
        
        total_delta = 0
        total_gamma = 0
        total_theta = 0
        total_vega = 0
        max_loss = 0
        long_count = 0
        short_count = 0
        
        for pos in self.positions.values():
            qty = pos.quantity
            
            total_delta += pos.delta * qty
            total_gamma += pos.gamma * qty
            total_theta += pos.theta * qty
            total_vega += pos.vega * qty
            
            if qty > 0:
                long_count += 1
                # Max loss for long = premium paid
                max_loss += pos.entry_price * qty
            else:
                short_count += 1
        
        # Calculate exposure percentages
        delta_exposure = abs(total_delta) / self.capital * 100 if self.capital > 0 else 0
        theta_burn = abs(total_theta) / self.capital * 100 if self.capital > 0 else 0
        vega_exposure = abs(total_vega) / self.capital * 100 if self.capital > 0 else 0
        
        self.current_greeks = PortfolioGreeks(
            total_delta=total_delta,
            total_gamma=total_gamma,
            total_theta=total_theta,
            total_vega=total_vega,
            position_count=len(self.positions),
            long_count=long_count,
            short_count=short_count,
            margin_used=max_loss,  # Simplified
            max_loss=max_loss,
            delta_exposure_pct=delta_exposure,
            theta_burn_pct=theta_burn,
            vega_exposure_pct=vega_exposure
        )
    
    def get_greeks(self) -> Optional[PortfolioGreeks]:
        """Get current portfolio Greeks."""
        return self.current_greeks
    
    def get_position_breakdown(self) -> List[Dict]:
        """Get breakdown by position."""
        return [
            {
                "id": pid,
                "symbol": pos.symbol,
                "strike": pos.strike,
                "type": pos.option_type,
                "qty": pos.quantity,
                "delta": round(pos.delta * pos.quantity, 2),
                "theta": round(pos.theta * pos.quantity, 2),
                "pnl": round(pos.unrealized_pnl, 2)
            }
            for pid, pos in self.positions.items()
        ]
    
    def is_delta_neutral(self, tolerance: float = 0.1) -> bool:
        """Check if portfolio is approximately delta neutral."""
        if not self.current_greeks:
            return True
        return abs(self.current_greeks.total_delta) < tolerance
    
    def get_delta_adjustment_needed(self) -> float:
        """Calculate delta adjustment needed for neutrality."""
        if not self.current_greeks:
            return 0
        return -self.current_greeks.total_delta
    
    def check_risk_limits(
        self,
        max_delta_pct: float = 5.0,
        max_theta_pct: float = 0.5,
        max_vega_pct: float = 2.0
    ) -> Dict[str, any]:
        """Check if portfolio exceeds risk limits."""
        if not self.current_greeks:
            return {"within_limits": True}
        
        g = self.current_greeks
        violations = []
        
        if g.delta_exposure_pct > max_delta_pct:
            violations.append(f"Delta exposure {g.delta_exposure_pct:.1f}% > {max_delta_pct}%")
        
        if g.theta_burn_pct > max_theta_pct:
            violations.append(f"Theta burn {g.theta_burn_pct:.2f}% > {max_theta_pct}%")
        
        if g.vega_exposure_pct > max_vega_pct:
            violations.append(f"Vega exposure {g.vega_exposure_pct:.1f}% > {max_vega_pct}%")
        
        return {
            "within_limits": len(violations) == 0,
            "violations": violations,
            "current": g.to_dict()
        }


# Singleton
greeks_portfolio_tracker = GreeksPortfolioTracker()

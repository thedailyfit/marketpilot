"""
Theta Budget Manager
Enforces daily theta budget for options buying.
"""
import logging
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import date


@dataclass
class ThetaBudgetStatus:
    """Current theta budget status."""
    daily_budget: float      # Max daily theta in rupees
    current_theta: float     # Current portfolio theta
    remaining_budget: float  # Available theta capacity
    utilization_pct: float   # % of budget used
    
    can_add_more: bool
    warning: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "budget": self.daily_budget,
            "current": round(self.current_theta, 2),
            "remaining": round(self.remaining_budget, 2),
            "utilization": round(self.utilization_pct, 1),
            "can_add_more": self.can_add_more,
            "warning": self.warning
        }


class ThetaBudgetManager:
    """
    Enforces daily theta budget for options buying.
    
    Purpose:
    - Prevents over-exposure to time decay
    - Forces position sizing discipline
    - Protects capital during flat markets
    
    Rules:
    - Max daily theta = X rupees (configurable)
    - Warning at 80% utilization
    - Block new positions at 100%
    - Suggest size reduction if exceeding
    """
    
    def __init__(self, daily_budget: float = 500.0):
        self.logger = logging.getLogger("ThetaBudgetManager")
        self.daily_budget = daily_budget  # ₹500 default
        self.current_theta = 0.0
        
        # History for analysis
        self.daily_history: Dict[str, float] = {}
    
    def set_budget(self, budget: float):
        """Update daily theta budget."""
        self.daily_budget = budget
        self.logger.info(f"Theta budget set to ₹{budget}/day")
    
    def update_current_theta(self, theta: float):
        """Update current portfolio theta."""
        self.current_theta = abs(theta)  # Always positive for budget tracking
    
    def get_status(self) -> ThetaBudgetStatus:
        """Get current budget status."""
        remaining = max(0, self.daily_budget - self.current_theta)
        utilization = (self.current_theta / self.daily_budget * 100) if self.daily_budget > 0 else 0
        
        warning = None
        if utilization >= 100:
            warning = "BLOCKED: Theta budget exhausted"
        elif utilization >= 80:
            warning = "WARNING: Theta budget nearly exhausted"
        elif utilization >= 60:
            warning = "CAUTION: Over 60% theta budget used"
        
        return ThetaBudgetStatus(
            daily_budget=self.daily_budget,
            current_theta=self.current_theta,
            remaining_budget=remaining,
            utilization_pct=utilization,
            can_add_more=remaining > 0,
            warning=warning
        )
    
    def can_add_position(
        self,
        new_position_theta: float
    ) -> Dict[str, any]:
        """
        Check if new position can be added within theta budget.
        
        Args:
            new_position_theta: Daily theta of new position (positive value)
        
        Returns:
            Dict with allowed, reason, and suggested adjustments
        """
        new_theta = abs(new_position_theta)
        projected_theta = self.current_theta + new_theta
        
        if projected_theta > self.daily_budget:
            # Calculate how much to reduce
            max_allowed = self.daily_budget - self.current_theta
            reduction_needed = new_theta - max_allowed
            
            return {
                "allowed": False,
                "reason": f"Theta budget exceeded: ₹{projected_theta:.0f} > ₹{self.daily_budget:.0f}",
                "current_theta": round(self.current_theta, 2),
                "new_theta": round(new_theta, 2),
                "projected": round(projected_theta, 2),
                "budget": self.daily_budget,
                "max_allowed_theta": round(max(0, max_allowed), 2),
                "suggestion": f"Reduce position by {reduction_needed/new_theta*100:.0f}% or use ITM options"
            }
        
        # Warning zone
        utilization = projected_theta / self.daily_budget * 100
        
        if utilization > 80:
            return {
                "allowed": True,
                "warning": f"High theta utilization: {utilization:.0f}%",
                "remaining_after": round(self.daily_budget - projected_theta, 2),
                "recommendation": "Consider limiting further positions today"
            }
        
        return {
            "allowed": True,
            "remaining_after": round(self.daily_budget - projected_theta, 2)
        }
    
    def calculate_max_quantity(
        self,
        theta_per_lot: float,
        desired_quantity: int
    ) -> Dict[str, int]:
        """
        Calculate maximum quantity within theta budget.
        
        Returns:
            Dict with max_quantity and recommendation
        """
        if theta_per_lot <= 0:
            return {"max_quantity": desired_quantity, "limited_by_theta": False}
        
        remaining_budget = self.daily_budget - self.current_theta
        
        if remaining_budget <= 0:
            return {
                "max_quantity": 0,
                "limited_by_theta": True,
                "reason": "No theta budget remaining"
            }
        
        max_lots = int(remaining_budget / theta_per_lot)
        
        if max_lots >= desired_quantity:
            return {"max_quantity": desired_quantity, "limited_by_theta": False}
        
        return {
            "max_quantity": max_lots,
            "limited_by_theta": True,
            "original_request": desired_quantity,
            "theta_limit_reason": f"Theta budget allows only {max_lots} lots"
        }
    
    def record_daily(self):
        """Record daily theta for historical analysis."""
        today = date.today().isoformat()
        self.daily_history[today] = self.current_theta
    
    def get_average_theta(self, days: int = 7) -> float:
        """Get average daily theta over last N days."""
        if not self.daily_history:
            return 0
        
        values = list(self.daily_history.values())[-days:]
        return sum(values) / len(values) if values else 0
    
    def suggest_budget_adjustment(self) -> Dict[str, any]:
        """Suggest budget adjustment based on history."""
        avg = self.get_average_theta()
        
        if avg > self.daily_budget * 0.9:
            return {
                "suggestion": "INCREASE",
                "reason": f"Average theta (₹{avg:.0f}) near budget limit",
                "recommended_budget": round(avg * 1.25, 0)
            }
        elif avg < self.daily_budget * 0.3:
            return {
                "suggestion": "DECREASE",
                "reason": f"Average theta (₹{avg:.0f}) well below budget",
                "recommended_budget": round(max(avg * 2, 200), 0)
            }
        
        return {
            "suggestion": "MAINTAIN",
            "reason": f"Current budget appropriate for usage pattern"
        }


# Singleton
theta_budget_manager = ThetaBudgetManager()

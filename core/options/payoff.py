"""
Payoff Simulator
Simulates option payoff under various scenarios including IV stress.
"""
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
from .greeks import black_scholes_price, calculate_greeks, days_to_years
from .chain_snapshot import OptionSnapshot


@dataclass
class PayoffScenario:
    """Single payoff scenario result."""
    spot_change_pct: float    # % change in spot
    iv_change_pct: float      # % change in IV
    days_forward: int         # Days into future
    new_spot: float
    new_iv: float
    new_price: float
    payoff: float             # P&L per lot
    payoff_pct: float         # P&L as % of entry
    probability: float        # Estimated probability
    scenario_name: str = ""


@dataclass
class StressTestResult:
    """Comprehensive stress test results."""
    option: OptionSnapshot
    entry_price: float
    
    # Core stress scenarios
    iv_crush_10: float        # P&L with 10% IV drop
    iv_crush_20: float        # P&L with 20% IV drop
    theta_1day: float         # P&L from 1 day decay
    theta_3day: float         # P&L from 3 day decay
    worst_case: float         # Combined adverse scenario
    
    # Break-even analysis
    breakeven_spot_up: float  # Spot needed to break even (for CE)
    breakeven_spot_down: float  # Spot needed to break even (for PE)
    
    # Risk metrics
    max_loss: float           # 100% premium
    risk_reward: float        # Target / Risk ratio
    
    def to_dict(self) -> dict:
        return {
            "strike": self.option.strike,
            "expiry": self.option.expiry,
            "type": self.option.option_type,
            "entry": self.entry_price,
            "iv_crush_10": round(self.iv_crush_10, 2),
            "iv_crush_20": round(self.iv_crush_20, 2),
            "theta_1day": round(self.theta_1day, 2),
            "theta_3day": round(self.theta_3day, 2),
            "worst_case": round(self.worst_case, 2),
            "breakeven_up": round(self.breakeven_spot_up, 2),
            "breakeven_down": round(self.breakeven_spot_down, 2),
            "max_loss": round(self.max_loss, 2),
            "risk_reward": round(self.risk_reward, 2)
        }


class PayoffSimulator:
    """
    Simulates option payoff under various scenarios.
    
    Features:
    - Spot price scenarios (-5% to +5%)
    - IV crush scenarios (-20%, -10%, 0%, +10%)
    - Time decay projections
    - Combined stress testing
    - Break-even analysis
    """
    
    def __init__(self):
        self.logger = logging.getLogger("PayoffSimulator")
        self.risk_free_rate = 0.07
        
        # Default scenario grids
        self.spot_scenarios = [-0.05, -0.03, -0.02, -0.01, 0, 0.01, 0.02, 0.03, 0.05]
        self.iv_scenarios = [-0.20, -0.10, 0, 0.10, 0.20]
        
    def simulate_payoff(
        self,
        option: OptionSnapshot,
        spot: float,
        spot_scenarios: Optional[List[float]] = None,
        iv_scenarios: Optional[List[float]] = None,
        days_forward: int = 0
    ) -> List[PayoffScenario]:
        """
        Simulate option payoff under multiple scenarios.
        
        Args:
            option: Option to simulate
            spot: Current spot price
            spot_scenarios: List of % changes [-0.05, 0, 0.05]
            iv_scenarios: List of IV % changes [-0.20, 0, 0.20]
            days_forward: Days to project forward
        
        Returns:
            List of PayoffScenario results
        """
        if spot_scenarios is None:
            spot_scenarios = self.spot_scenarios
        if iv_scenarios is None:
            iv_scenarios = self.iv_scenarios
        
        results = []
        entry_price = option.ltp
        
        # Calculate remaining time
        from datetime import date
        expiry_date = datetime.strptime(option.expiry, '%Y-%m-%d').date()
        days_left = (expiry_date - date.today()).days - days_forward
        
        if days_left < 0:
            days_left = 0
        
        time_to_expiry = days_to_years(max(1, days_left))
        
        for spot_delta in spot_scenarios:
            for iv_delta in iv_scenarios:
                new_spot = spot * (1 + spot_delta)
                new_iv = max(0.01, option.iv * (1 + iv_delta))
                
                # Calculate new option price
                new_price = black_scholes_price(
                    new_spot,
                    option.strike,
                    time_to_expiry,
                    new_iv,
                    self.risk_free_rate,
                    option.option_type
                )
                
                payoff = new_price - entry_price
                payoff_pct = (payoff / entry_price) * 100 if entry_price > 0 else 0
                
                # Estimate probability (simplified)
                prob = self._estimate_probability(spot_delta, iv_delta, option.iv)
                
                # Generate scenario name
                name = self._scenario_name(spot_delta, iv_delta, days_forward)
                
                results.append(PayoffScenario(
                    spot_change_pct=spot_delta * 100,
                    iv_change_pct=iv_delta * 100,
                    days_forward=days_forward,
                    new_spot=round(new_spot, 2),
                    new_iv=round(new_iv, 4),
                    new_price=round(new_price, 2),
                    payoff=round(payoff, 2),
                    payoff_pct=round(payoff_pct, 1),
                    probability=round(prob, 3),
                    scenario_name=name
                ))
        
        return results
    
    def stress_test(
        self,
        option: OptionSnapshot,
        spot: float
    ) -> StressTestResult:
        """
        Run standard stress scenarios for options buying.
        
        Returns key risk metrics:
        - IV crush impact (10%, 20%)
        - Theta decay (1 day, 3 days)
        - Worst case (adverse spot + IV crush + time)
        - Break-even levels
        """
        entry_price = option.ltp
        
        # Current parameters
        from datetime import date
        expiry_date = datetime.strptime(option.expiry, '%Y-%m-%d').date()
        days_left = (expiry_date - date.today()).days
        
        # IV Crush scenarios
        iv_crush_10 = self._simulate_single(option, spot, 0, -0.10, 0)
        iv_crush_20 = self._simulate_single(option, spot, 0, -0.20, 0)
        
        # Theta decay
        theta_1day = self._simulate_single(option, spot, 0, 0, 1)
        theta_3day = self._simulate_single(option, spot, 0, 0, 3)
        
        # Worst case: wrong direction + IV crush + time
        if option.option_type == 'CE':
            worst_spot = -0.02  # 2% down for calls
        else:
            worst_spot = 0.02   # 2% up for puts
        
        worst_case = self._simulate_single(option, spot, worst_spot, -0.15, 2)
        
        # Break-even analysis
        breakeven_up, breakeven_down = self._find_breakeven(option, spot, days_left)
        
        # Risk-reward (assuming 2x target)
        max_loss = entry_price
        target = entry_price * 2  # 100% gain target
        risk_reward = target / max_loss if max_loss > 0 else 0
        
        return StressTestResult(
            option=option,
            entry_price=entry_price,
            iv_crush_10=iv_crush_10,
            iv_crush_20=iv_crush_20,
            theta_1day=theta_1day,
            theta_3day=theta_3day,
            worst_case=worst_case,
            breakeven_spot_up=breakeven_up,
            breakeven_spot_down=breakeven_down,
            max_loss=max_loss,
            risk_reward=risk_reward
        )
    
    def _simulate_single(
        self,
        option: OptionSnapshot,
        spot: float,
        spot_delta: float,
        iv_delta: float,
        days_forward: int
    ) -> float:
        """Simulate single scenario and return payoff."""
        entry_price = option.ltp
        
        from datetime import date
        expiry_date = datetime.strptime(option.expiry, '%Y-%m-%d').date()
        days_left = (expiry_date - date.today()).days - days_forward
        
        if days_left < 0:
            # At expiry
            new_spot = spot * (1 + spot_delta)
            if option.option_type == 'CE':
                return max(0, new_spot - option.strike) - entry_price
            else:
                return max(0, option.strike - new_spot) - entry_price
        
        time_to_expiry = days_to_years(max(1, days_left))
        new_spot = spot * (1 + spot_delta)
        new_iv = max(0.01, option.iv * (1 + iv_delta))
        
        new_price = black_scholes_price(
            new_spot,
            option.strike,
            time_to_expiry,
            new_iv,
            self.risk_free_rate,
            option.option_type
        )
        
        return new_price - entry_price
    
    def _find_breakeven(
        self,
        option: OptionSnapshot,
        spot: float,
        days_left: int
    ) -> tuple:
        """Find break-even spot levels."""
        entry_price = option.ltp
        
        # Search for break-even
        breakeven_up = spot
        breakeven_down = spot
        
        # Binary search for upside break-even
        low, high = spot, spot * 1.10
        for _ in range(20):
            mid = (low + high) / 2
            payoff = self._simulate_single(option, mid, 0, 0, 0)
            if abs(payoff) < 1:  # Within ₹1
                breakeven_up = mid
                break
            if payoff > 0:
                high = mid
            else:
                low = mid
        else:
            breakeven_up = mid
        
        # Binary search for downside break-even
        low, high = spot * 0.90, spot
        for _ in range(20):
            mid = (low + high) / 2
            payoff = self._simulate_single(option, mid, 0, 0, 0)
            if abs(payoff) < 1:
                breakeven_down = mid
                break
            if payoff > 0:
                low = mid
            else:
                high = mid
        else:
            breakeven_down = mid
        
        return breakeven_up, breakeven_down
    
    def _estimate_probability(
        self,
        spot_delta: float,
        iv_delta: float,
        current_iv: float
    ) -> float:
        """Rough probability estimate for scenario."""
        # Very simplified - use historical data in production
        
        # Spot probability (normal distribution approximation)
        import math
        spot_prob = math.exp(-(spot_delta ** 2) / (2 * current_iv ** 2))
        
        # IV change probability (skewed towards crush)
        if iv_delta < 0:
            iv_prob = 0.6  # Crush more likely
        else:
            iv_prob = 0.4
        
        return spot_prob * 0.7 + iv_prob * 0.3
    
    def _scenario_name(
        self,
        spot_delta: float,
        iv_delta: float,
        days_forward: int
    ) -> str:
        """Generate human-readable scenario name."""
        parts = []
        
        if spot_delta > 0:
            parts.append(f"Spot +{spot_delta*100:.0f}%")
        elif spot_delta < 0:
            parts.append(f"Spot {spot_delta*100:.0f}%")
        else:
            parts.append("Spot flat")
        
        if iv_delta > 0:
            parts.append(f"IV +{iv_delta*100:.0f}%")
        elif iv_delta < 0:
            parts.append(f"IV {iv_delta*100:.0f}%")
        
        if days_forward > 0:
            parts.append(f"+{days_forward}d")
        
        return " | ".join(parts)
    
    def generate_payoff_matrix(
        self,
        option: OptionSnapshot,
        spot: float
    ) -> Dict[str, any]:
        """
        Generate payoff matrix for UI display.
        
        Returns matrix where:
        - Rows = Spot scenarios
        - Cols = IV scenarios
        - Values = P&L
        """
        results = self.simulate_payoff(option, spot)
        
        # Build matrix
        matrix = {}
        for r in results:
            spot_key = f"{r.spot_change_pct:+.0f}%"
            if spot_key not in matrix:
                matrix[spot_key] = {}
            
            iv_key = f"IV {r.iv_change_pct:+.0f}%"
            matrix[spot_key][iv_key] = r.payoff
        
        return {
            "matrix": matrix,
            "entry": option.ltp,
            "strike": option.strike,
            "expiry": option.expiry,
            "type": option.option_type
        }
    
    def should_avoid_trade(
        self,
        stress_result: StressTestResult,
        max_acceptable_crush_loss: float = 0.30
    ) -> tuple:
        """
        Determine if trade should be avoided based on stress test.
        
        Args:
            stress_result: Stress test results
            max_acceptable_crush_loss: Max acceptable loss from IV crush (e.g., 0.30 = 30%)
        
        Returns:
            (should_avoid, reason)
        """
        entry = stress_result.entry_price
        
        # Check IV crush risk
        crush_loss_pct = abs(stress_result.iv_crush_10) / entry if entry > 0 else 0
        if crush_loss_pct > max_acceptable_crush_loss:
            return True, f"High IV crush risk: {crush_loss_pct*100:.0f}% loss on 10% IV drop"
        
        # Check theta decay
        theta_loss_pct = abs(stress_result.theta_1day) / entry if entry > 0 else 0
        if theta_loss_pct > 0.10:  # >10% per day
            return True, f"Excessive theta: {theta_loss_pct*100:.0f}% daily decay"
        
        # Check worst case
        worst_loss_pct = abs(stress_result.worst_case) / entry if entry > 0 else 0
        if worst_loss_pct > 0.50:  # >50% worst case
            return True, f"Unfavorable worst case: {worst_loss_pct*100:.0f}% potential loss"
        
        # Check risk-reward
        if stress_result.risk_reward < 1.5:
            return True, f"Poor risk-reward: {stress_result.risk_reward:.1f}x"
        
        return False, "Stress test passed"


# Singleton
payoff_simulator = PayoffSimulator()

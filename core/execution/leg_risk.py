"""
Leg Risk Simulator
Simulates execution risk (slippage/legging risk) for multi-leg strategies.
"""
import logging
from dataclasses import dataclass
from core.options.chain_snapshot import OptionSnapshot

@dataclass
class LegRiskReport:
    """Report on potential execution risks."""
    is_safe: bool
    estimated_slippage: float
    worst_case_loss: float
    reason: str
    warnings: list

class LegRiskSimulator:
    """
    Simulates worst-case scenarios during trade execution.
    """
    def __init__(self):
        self.logger = logging.getLogger("LegRiskSimulator")
        
    def assess_legging_risk(
        self, 
        long_leg: OptionSnapshot,
        short_leg: OptionSnapshot,
        max_risk_budget: float
    ) -> LegRiskReport:
        """
        Assess risk of legging into the spread.
        
        Scenarios:
        1. Long leg fills, Market moves, Short leg fills at worse price.
        2. Bid-Ask spread widening during execution.
        """
        warnings = []
        
        # 1. Slippage Estimation (Conservative)
        # Assume we pay Ask for Long, receive Bid for Short.
        # Slippage risk: The 'Bid' for short leg might drop before we fill it.
        # Or 'Ask' for long leg might rise.
        # Let's estimate slippage as 10% of the Short Leg premium (volatility buffer)
        # plus fixed tick slippage.
        
        short_slippage = (short_leg.ltp * 0.10) + 1.0 # 10% + 1 rupee
        long_slippage = (long_leg.ltp * 0.02) + 0.5 # 2% + 0.5 rupee (Long is usually first/market)
        
        total_slippage_risk = short_slippage + long_slippage
        
        # 2. Liquidity Check
        if short_leg.oi < 5000:
            warnings.append(f"Low OI on Short Leg ({short_leg.oi}). Slippage may be higher.")
            total_slippage_risk *= 1.5
            
        if (short_leg.ask - short_leg.bid) > (short_leg.ltp * 0.1):
            warnings.append("Wide spread on Short Leg. Execution risk high.")
            total_slippage_risk *= 1.2
            
        # 3. Worst-Case Cost Analysis
        nominal_debit = long_leg.ask - short_leg.bid
        worst_case_debit = nominal_debit + total_slippage_risk
        
        is_safe = True
        reason = "Execution risk within tolerance."
        
        if worst_case_debit > max_risk_budget:
            is_safe = False
            reason = (
                f"Worst-case debit ({worst_case_debit:.2f}) exceeds risk budget "
                f"({max_risk_budget:.2f}). Slippage risk: {total_slippage_risk:.2f}"
            )
        
        return LegRiskReport(
            is_safe=is_safe,
            estimated_slippage=round(total_slippage_risk, 2),
            worst_case_loss=round(worst_case_debit, 2),
            reason=reason,
            warnings=warnings
        )

# Singleton
leg_risk_simulator = LegRiskSimulator()

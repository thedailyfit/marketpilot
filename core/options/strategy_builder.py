"""
Multi-Leg Strategy Builder
Converts naked option ideas into defined-risk vertical spreads.
"""
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from core.options.chain_snapshot import OptionSnapshot

@dataclass
class SpreadStructure:
    """Standard definition of a vertical spread."""
    name: str # e.g., "BULL_CALL_SPREAD"
    long_leg: OptionSnapshot
    short_leg: OptionSnapshot
    net_debit: float
    max_loss: float
    max_gain: float
    breakeven: float
    width: float
    risk_reward_ratio: float
    legs: List[OptionSnapshot]

class MultiLegStrategyBuilder:
    """
    Constructs multi-leg strategies from base ideas.
    """
    def __init__(self):
        self.logger = logging.getLogger("MultiLegBuilder")
        
    def build_vertical_spread(
        self,
        base_option: OptionSnapshot,
        direction: str,  # "BULLISH" or "BEARISH"
        chain: List[OptionSnapshot],
        risk_budget: float,
        min_width: float = 50.0 # Minimum strike width
    ) -> Optional[SpreadStructure]:
        """
        Converts a naked option (base_option) into a Vertical Debit Spread.
        
        Logic:
        1. Keep base_option as the Long Leg.
        2. Find a Short Leg to reduce cost and cap risk.
        3. Ensure Net Debit <= Risk Budget (if possible).
        """
        
        # 1. Filter chain for potential short legs
        # Same expiry, same type
        candidates = [
            opt for opt in chain 
            if opt.expiry == base_option.expiry 
            and opt.option_type == base_option.option_type
            and opt.symbol == base_option.symbol
        ]
        
        if not candidates:
            self.logger.warning(f"No candidates for spread construction for {base_option.symbol}")
            return None
            
        long_strike = base_option.strike
        target_short_leg = None
        
        # 2. Select Short Leg based on direction
        if direction == "BULLISH" and base_option.option_type == "CE":
            # Bull Call Spread: Long Lower Strike, Short Higher Strike
            # Find strikes > long_strike
            short_candidates = sorted(
                [opt for opt in candidates if opt.strike > long_strike],
                key=lambda x: x.strike
            )
            spread_type = "BULL_CALL_SPREAD"
            
        elif direction == "BEARISH" and base_option.option_type == "PE":
            # Bear Put Spread: Long Higher Strike, Short Lower Strike
            # Find strikes < long_strike
            short_candidates = sorted(
                [opt for opt in candidates if opt.strike < long_strike],
                key=lambda x: x.strike,
                reverse=True # Sort descending (closest lower strike first)
            )
            spread_type = "BEAR_PUT_SPREAD"
            
        else:
            self.logger.error(f"Invalid direction/type combo: {direction}/{base_option.option_type}")
            return None
            
        if not short_candidates:
            self.logger.warning("No valid strikes for short leg found.")
            return None
            
        # 3. Optimize Short Leg Selection
        # We want to reduce cost significantly but leave room for profit.
        # Simple heuristic: Sell the option that is ~1-2 strikes away OR delta ~0.30
        
        chosen_short = None
        
        for candidate in short_candidates:
            width = abs(candidate.strike - long_strike)
            if width < min_width:
                continue
                
            # Check liquidity of short leg
            if candidate.volume < 100 or candidate.oi < 1000:
                continue
                
            # Check cost reduction
            # Long Leg Cost: Ask Price
            # Short Leg Credit: Bid Price
            cost = base_option.ask
            credit = candidate.bid
            net_debit = cost - credit
            
            # If this brings us within risk budget, it's a strong candidate
            if net_debit <= risk_budget:
                chosen_short = candidate
                break # Found the nearest valid one
                
        # If no short leg found that meets budget, pick the one that reduces cost the most
        # while maintaining minimum width? Or just fail?
        # User constraint: "If leg risk cannot be bounded -> BLOCK trade"
        # Since this is a Debit Spread, risk is bounded to Net Debit.
        # If Net Debit > Risk Budget, we should probably fail or pick a wider spread?
        # Actually, a wider spread costs MORE (less credit received).
        # A NARROWER spread costs LESS (more credit received).
        
        # Wait, Vertical Debit Spread:
        # Long ITM/ATM, Short OTM.
        # Closer Short Strike = More Credit = Lower Net Debit = Lower Risk.
        # But also Lower Max Profit.
        
        # If we failed to find a leg that meets budget (meaning even narrowing didn't help, or we ran out of strikes),
        # we might need to select a *different* long leg. But prompt says "Base Option" is input.
        
        if not chosen_short:
            # Fallback: Just pick the first valid liquid strike to define risk, even if over budget?
            # No, prompt says "If max loss exceeds allowed budget: BLOCK trade".
            # So if we can't construct a spread within budget, we return None (Trade Blocked).
            self.logger.warning("Could not construct spread within risk budget.")
            return None
            
        # 4. Construct Spread Structure
        long_cost = base_option.ask
        short_credit = chosen_short.bid
        net_debit = long_cost - short_credit
        width = abs(long_strike - chosen_short.strike)
        
        max_loss = net_debit
        max_gain = width - net_debit
        
        # Breakeven
        if spread_type == "BULL_CALL_SPREAD":
            breakeven = long_strike + net_debit
        else: # BEAR_PUT_SPREAD
            breakeven = long_strike - net_debit
            
        rr_ratio = max_gain / max_loss if max_loss > 0 else 0
        
        return SpreadStructure(
            name=spread_type,
            long_leg=base_option,
            short_leg=chosen_short,
            net_debit=round(net_debit, 2),
            max_loss=round(max_loss, 2),
            max_gain=round(max_gain, 2),
            breakeven=round(breakeven, 2),
            width=width,
            risk_reward_ratio=round(rr_ratio, 2),
            legs=[base_option, chosen_short]
        )

# Singleton
strategy_builder = MultiLegStrategyBuilder()

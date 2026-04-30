"""
Multi-Leg Executor
Executes complex option structures (Spreads, Iron Condors) with leg risk management.
"""
import logging
import asyncio
from dataclasses import dataclass
from typing import List, Dict

from .smart_order import SmartOrderEngine, ExecutionRequest, Urgency

@dataclass
class Leg:
    symbol: str
    action: str  # BUY/SELL
    quantity: int
    strike: float
    option_type: str  # CE/PE
    
    @property
    def is_buy(self):
        return self.action == "BUY"

@dataclass
class SpreadOrder:
    strategy_type: str  # VERTICAL, IRON_CONDOR, etc.
    legs: List[Leg]
    net_quantity: int
    urgency: Urgency = Urgency.BALANCED

class MultiLegExecutor:
    """
    Executes complex option structures.
    
    Logic:
    - Identifies "Hard Leg" (usually Short/Sell leg or ITM leg).
    - Submits Hard Leg first.
    - Upon fill, fires "Easy Leg" (Buy/OTM) immediately/aggressively to hedge.
    - Monitors specifically for "Legged Out" risk (one filled, one failed).
    """
    
    def __init__(self):
        self.logger = logging.getLogger("MultiLegExecutor")
        
    def plan_execution(self, spread: SpreadOrder) -> List[Leg]:
        """
        Order legs by execution priority (Hardest -> Easiest).
        
        General Rule:
        1. Short legs first (Credit) -> Harder to fill at good price.
        2. ITM legs -> Less liquidity.
        3. Long legs last (Debit) -> Easier to fill (hedges).
        """
        # Sort legs: SELL first, then BUY
        # Valid assumption for credit spreads and debit spreads (sell gives liquidity constraint)
        sorted_legs = sorted(spread.legs, key=lambda l: 0 if l.action == "SELL" else 1)
        return sorted_legs
    
    async def execute_spread(
        self,
        spread: SpreadOrder,
        execute_func  # Callback to execute single leg
    ) -> Dict:
        """
        Execute spread by legging in.
        
        Args:
            spread: Spread def
            execute_func: async func(symbol, action, qty, urgency) -> Result
        """
        legs = self.plan_execution(spread)
        results = []
        fill_status = "PENDING"
        
        # Execute Hard Leg (First)
        hard_leg = legs[0]
        self.logger.info(f"🧱 Executing HARD LEG: {hard_leg.action} {hard_leg.symbol}")
        
        # Hard leg gets requested urgency
        res1 = await execute_func(
            hard_leg.symbol, 
            hard_leg.action, 
            hard_leg.quantity, 
            spread.urgency
        )
        results.append(res1)
        
        if res1.get('status') != 'FILLED':
            self.logger.warning(f"❌ Hard leg failed/cancelled. Aborting spread.")
            return {"status": "FAILED", "results": results}
        
        # Execute Easy Leg (Second)
        easy_leg = legs[1]
        self.logger.info(f"🚀 Executing EASY LEG (Hedge): {easy_leg.action} {easy_leg.symbol}")
        
        # Easy leg gets AGGRESSIVE urgency to ensure hedge happens
        res2 = await execute_func(
            easy_leg.symbol, 
            easy_leg.action, 
            easy_leg.quantity, 
            Urgency.AGGRESSIVE
        )
        results.append(res2)
        
        if res2.get('status') != 'FILLED':
            self.logger.critical(f"🚨 LEG RISK! Hard leg filled, Easy leg failed! Manual Intervention Required!")
            return {"status": "LEGGED_OUT_RISK", "results": results}
        
        return {"status": "FILLED", "results": results}

# Singleton
multi_leg_executor = MultiLegExecutor()

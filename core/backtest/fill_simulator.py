"""
Fill Simulator
Realistic option fill simulation using historical bid-ask spreads.
"""
import logging
import random
from dataclasses import dataclass
from typing import Optional
from enum import Enum

from core.options import OptionSnapshot


class Aggression(Enum):
    """Order aggression level."""
    PASSIVE = "PASSIVE"    # Bid/Ask + queue wait (best price, may not fill)
    NORMAL = "NORMAL"      # Mid + small slippage (likely fill)
    AGGRESSIVE = "AGGRESSIVE"  # Cross spread (certain fill, worst price)


@dataclass
class FillResult:
    """Result of fill simulation."""
    filled: bool
    fill_price: float
    slippage: float          # Price moved against us
    slippage_pct: float      # Slippage as percentage
    spread_cost: float       # Half spread paid
    spread_cost_pct: float   # Spread cost as percentage
    queue_position: float    # 0-1, position in queue (PASSIVE only)
    partial_qty: int         # Quantity filled (for partial fills)
    reason: str              # Fill reason
    
    def to_dict(self) -> dict:
        return {
            "filled": self.filled,
            "fill_price": round(self.fill_price, 2),
            "slippage": round(self.slippage, 2),
            "slippage_pct": round(self.slippage_pct, 4),
            "spread_cost": round(self.spread_cost, 2),
            "spread_cost_pct": round(self.spread_cost_pct, 4),
            "queue_position": round(self.queue_position, 2),
            "partial_qty": self.partial_qty,
            "reason": self.reason
        }


class FillSimulator:
    """
    Realistic option fill simulator.
    
    Features:
    - Uses historical bid-ask spread (not fixed %)
    - Models slippage as probability distribution
    - Accounts for OTM depth (wider spreads)
    - Simulates partial fills
    - Models queue priority for PASSIVE orders
    
    Slippage Distribution (Indian markets):
    - ATM: 0.3-0.5%
    - 1-2 OTM: 0.5-1%
    - 3+ OTM: 1-2%
    - Deep OTM: 2-5%
    """
    
    # Slippage parameters by aggression
    SLIPPAGE_PARAMS = {
        Aggression.PASSIVE: {"mean": 0.0, "std": 0.001},
        Aggression.NORMAL: {"mean": 0.003, "std": 0.002},
        Aggression.AGGRESSIVE: {"mean": 0.008, "std": 0.004}
    }
    
    # Fill probability by aggression
    FILL_PROB = {
        Aggression.PASSIVE: 0.6,     # 60% chance of fill
        Aggression.NORMAL: 0.95,     # 95% chance
        Aggression.AGGRESSIVE: 1.0   # 100% guaranteed
    }
    
    def __init__(self):
        self.logger = logging.getLogger("FillSimulator")
        
        # Stats tracking
        self.total_fills = 0
        self.total_slippage = 0.0
        self.total_spread_cost = 0.0
        self.failed_fills = 0
    
    def simulate_fill(
        self,
        snapshot: OptionSnapshot,
        side: str,
        quantity: int,
        aggression: Aggression = Aggression.NORMAL,
        spot_price: float = None
    ) -> FillResult:
        """
        Simulate a realistic fill.
        
        Args:
            snapshot: Option state at order time
            side: BUY or SELL
            quantity: Number of lots
            aggression: Order aggression level
            spot_price: Current spot (for OTM calculation)
        
        Returns:
            FillResult with fill details
        """
        bid = snapshot.bid
        ask = snapshot.ask
        mid = (bid + ask) / 2
        spread = ask - bid
        spread_pct = spread / mid if mid > 0 else 0.1
        
        # Determine if fill occurs
        fill_prob = self.FILL_PROB[aggression]
        
        # Reduce fill prob for wide spreads (illiquid options)
        if spread_pct > 0.05:  # >5% spread
            fill_prob *= 0.7
        elif spread_pct > 0.10:  # >10% spread
            fill_prob *= 0.4
        
        filled = random.random() < fill_prob
        
        if not filled:
            self.failed_fills += 1
            return FillResult(
                filled=False,
                fill_price=0.0,
                slippage=0.0,
                slippage_pct=0.0,
                spread_cost=0.0,
                spread_cost_pct=0.0,
                queue_position=1.0,
                partial_qty=0,
                reason="Order not filled (illiquid or queue not reached)"
            )
        
        # Calculate base fill price
        if aggression == Aggression.PASSIVE:
            # At bid/ask, best price
            base_price = ask if side == "BUY" else bid
            queue_position = random.uniform(0.3, 1.0)
        elif aggression == Aggression.NORMAL:
            # Mid + slight slippage
            base_price = mid + (spread * 0.25) if side == "BUY" else mid - (spread * 0.25)
            queue_position = 0.0
        else:  # AGGRESSIVE
            # Cross spread fully
            base_price = ask if side == "BUY" else bid
            queue_position = 0.0
        
        # Add random slippage
        params = self.SLIPPAGE_PARAMS[aggression]
        slippage_pct = abs(random.gauss(params["mean"], params["std"]))
        
        # Adjust slippage for OTM depth (wider slippage for illiquid OTM)
        if spot_price:
            otm_depth = abs(snapshot.strike - spot_price) / spot_price
            if otm_depth > 0.02:  # >2% OTM
                slippage_pct *= (1 + otm_depth * 10)  # Scale slippage
        
        # Calculate final fill price
        if side == "BUY":
            fill_price = base_price * (1 + slippage_pct)
            slippage = fill_price - base_price
        else:
            fill_price = base_price * (1 - slippage_pct)
            slippage = base_price - fill_price
        
        # Spread cost = half spread (always pay half)
        spread_cost = spread / 2
        spread_cost_pct = spread_cost / mid if mid > 0 else 0
        
        # Simulate partial fills for large orders
        partial_qty = quantity
        if quantity > 100:  # Large order
            fill_ratio = random.uniform(0.7, 1.0)
            partial_qty = max(1, int(quantity * fill_ratio))
        
        # Track stats
        self.total_fills += 1
        self.total_slippage += slippage * partial_qty
        self.total_spread_cost += spread_cost * partial_qty
        
        return FillResult(
            filled=True,
            fill_price=round(fill_price, 2),
            slippage=round(slippage, 2),
            slippage_pct=round(slippage_pct, 4),
            spread_cost=round(spread_cost, 2),
            spread_cost_pct=round(spread_cost_pct, 4),
            queue_position=queue_position,
            partial_qty=partial_qty,
            reason=f"Filled @ {aggression.value}"
        )
    
    def estimate_execution_cost(
        self,
        snapshot: OptionSnapshot,
        side: str,
        quantity: int,
        aggression: Aggression = Aggression.NORMAL
    ) -> dict:
        """
        Estimate total execution cost without simulating.
        
        Returns:
            Dict with estimated costs
        """
        mid = (snapshot.bid + snapshot.ask) / 2
        spread = snapshot.ask - snapshot.bid
        spread_pct = spread / mid if mid > 0 else 0.1
        
        # Estimated slippage
        params = self.SLIPPAGE_PARAMS[aggression]
        est_slippage_pct = params["mean"]
        
        # Cost per contract
        spread_cost_per = spread / 2
        slippage_per = mid * est_slippage_pct
        
        total_cost = (spread_cost_per + slippage_per) * quantity
        
        return {
            "spread_cost": round(spread_cost_per * quantity, 2),
            "slippage_cost": round(slippage_per * quantity, 2),
            "total_execution_cost": round(total_cost, 2),
            "cost_pct": round((spread_pct / 2 + est_slippage_pct) * 100, 2)
        }
    
    def get_stats(self) -> dict:
        """Get fill simulation statistics."""
        avg_slippage = self.total_slippage / self.total_fills if self.total_fills > 0 else 0
        avg_spread = self.total_spread_cost / self.total_fills if self.total_fills > 0 else 0
        
        return {
            "total_fills": self.total_fills,
            "failed_fills": self.failed_fills,
            "fill_rate": round(self.total_fills / (self.total_fills + self.failed_fills) * 100, 1) if (self.total_fills + self.failed_fills) > 0 else 0,
            "total_slippage": round(self.total_slippage, 2),
            "avg_slippage": round(avg_slippage, 2),
            "total_spread_cost": round(self.total_spread_cost, 2),
            "avg_spread_cost": round(avg_spread, 2)
        }
    
    def reset_stats(self):
        """Reset fill statistics."""
        self.total_fills = 0
        self.total_slippage = 0.0
        self.total_spread_cost = 0.0
        self.failed_fills = 0


# Singleton
fill_simulator = FillSimulator()

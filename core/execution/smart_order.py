"""
Smart Order Engine
Intelligent single-leg order execution with urgency control.
"""
import logging
import asyncio
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict

# In a real system, we'd import the broker client
# But since actual broker logic is in ExecutionAgent, we'll return instructions

class Urgency(Enum):
    PASSIVE = "PASSIVE"       # Sit on Bid/Ask, wait for fill
    BALANCED = "BALANCED"     # Mid-point peg, drift to Aggressive
    AGGRESSIVE = "AGGRESSIVE" # Market/Cross spread immediately


@dataclass
class ExecutionRequest:
    symbol: str
    action: str  # BUY/SELL
    quantity: int
    urgency: Urgency
    limit_price: float = 0.0  # Optional limit cap
    tag: str = "SMART_EXEC"


@dataclass
class ExecutionResult:
    order_id: str
    status: str      # FILLED, PARTIAL, CANCELLED, FAILED
    fill_price: float
    filled_quantity: int
    slippage: float
    message: str


class SmartOrderEngine:
    """
    Intelligent order placement engine.
    
    Strategies:
    - PASSIVE: Place Limit @ Best Bid/Ask. Wait 5s. Cancel/Modify.
    - BALANCED: Place Limit @ Mid. Wait 3s. Move to Best Bid/Ask.
    - AGGRESSIVE: Place Limit @ Best Ask/Bid + Buffer (Market protection).
    """
    
    def __init__(self):
        self.logger = logging.getLogger("SmartOrderEngine")
    
    def get_placement_params(
        self,
        request: ExecutionRequest,
        market_data: Dict
    ) -> Dict:
        """
        Determine optimal price and type based on market data and urgency.
        
        Args:
            request: Execution params
            market_data: {ltp, bid, ask, spread}
        
        Returns:
            Dict {order_type, price, validity}
        """
        bid = market_data.get('bid', 0)
        ask = market_data.get('ask', 0)
        ltp = market_data.get('ltp', 0)
        spread = ask - bid
        
        # Fallback if no depth data
        if bid == 0 or ask == 0:
            self.logger.warning("No depth data, falling back to LTP/Market")
            if request.urgency == Urgency.PASSIVE:
                price = ltp
            else:
                price = 0.0  # Market
            return {"order_type": "LIMIT" if price > 0 else "MARKET", "price": price}
        
        price = 0.0
        order_type = "LIMIT"
        
        if request.urgency == Urgency.PASSIVE:
            # Sit on best side
            if request.action == "BUY":
                price = bid + 0.05  # Join best bid + tick
            else:
                price = ask - 0.05  # Join best ask - tick
                
        elif request.urgency == Urgency.BALANCED:
            # Try midpoint
            mid = (bid + ask) / 2
            price = round(mid, 2)
            
        elif request.urgency == Urgency.AGGRESSIVE:
            # Cross spread with protection
            if request.action == "BUY":
                price = ask + (spread * 0.1)  # Ask + 10% spread buffer
            else:
                price = bid - (spread * 0.1)  # Bid - 10% spread buffer
            
            # Use market if preferred, but limit is safer
            # order_type = "MARKET" 
        
        # Cap at limit price if provided
        if request.limit_price > 0:
            if request.action == "BUY":
                price = min(price, request.limit_price)
            else:
                price = max(price, request.limit_price)
        
        return {
            "order_type": order_type,
            "price": round(price, 2),
            "validity": "DAY"
        }

# Singleton
smart_order_engine = SmartOrderEngine()

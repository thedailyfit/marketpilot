"""
Mock Broker
Simulates exchange matching engine and order management.
"""
import logging
from typing import Dict, List, Optional
from core.strategy.signal import Signal
from core.analytics.trade_journal import JournalEntry

class Order:
    def __init__(self, signal: Signal, order_id: str):
        self.order_id = order_id
        self.signal = signal
        self.status = "OPEN" # OPEN, FILLED, CANCELLED
        self.fill_price = 0.0
        self.fill_time = 0

class MockBroker:
    """
    Simulates order execution logic.
    """
    def __init__(self, initial_capital: float = 100000.0):
        self.logger = logging.getLogger("MockBroker")
        self.capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, int] = {} # Symbol -> Quantity
        self.open_orders: List[Order] = []
        self.trade_history: List[Dict] = []
        self.order_counter = 0
        
        # Costs
        self.commission_per_order = 20.0
        self.slippage_pct = 0.0005 # 0.05%
        
    def place_order(self, signal: Signal) -> str:
        """Accept a strategy signal as an order."""
        self.order_counter += 1
        order_id = f"ORD-{self.order_counter}"
        order = Order(signal, order_id)
        self.open_orders.append(order)
        # self.logger.info(f"Order Placed: {signal.action} {signal.quantity} {signal.symbol}")
        return order_id
        
    def process_bar(self, bar: Dict[str, Any]):
        """
        Match open orders against current bar High/Low.
        """
        symbol = bar['symbol']
        high = bar['high']
        low = bar['low']
        open_p = bar['open']
        
        # Iterate copy to maintain safety during removal
        for order in self.open_orders[:]:
            if order.signal.symbol != symbol:
                continue
                
            is_fill = False
            fill_price = 0.0
            
            # Simple Matching Logic
            # MARKET ORDER: Fills at Open (if order placed previous close) 
            # or Next Bar Open (typical backtest assumption: signal on close, trade on next open)
            # For simplicity, if limit_price is 0, we assume Market Order filling at Open price of THIS bar
            # (assuming this bar is "next" bar after signal)
            
            if order.signal.limit_price <= 0:
                # Market Order
                fill_price = open_p
                is_fill = True
            else:
                # Limit Order
                price = order.signal.limit_price
                if order.signal.action == "BUY" and low <= price:
                    fill_price = min(open_p, price) if open_p < price else price # Better fill logic? Simplified to price cap.
                    fill_price = price # Strict limit fill
                    is_fill = True
                elif order.signal.action == "SELL" and high >= price:
                    fill_price = price
                    is_fill = True
                    
            if is_fill:
                self._execute_fill(order, fill_price, bar['timestamp'])
                self.open_orders.remove(order)
                
    def _execute_fill(self, order: Order, raw_price: float, timestamp: any):
        """Calculates costs and updates positions."""
        # Apply Slippage
        if order.signal.action == "BUY":
            price = raw_price * (1 + self.slippage_pct)
        else:
            price = raw_price * (1 - self.slippage_pct)
            
        qty = order.signal.quantity
        cost = price * qty
        comm = self.commission_per_order
        
        # Update Balance
        if order.signal.action == "BUY":
            self.cash -= (cost + comm)
            self.positions[order.signal.symbol] = self.positions.get(order.signal.symbol, 0) + qty
        elif order.signal.action == "SELL":
            self.cash += (cost - comm)
            self.positions[order.signal.symbol] = self.positions.get(order.signal.symbol, 0) - qty
            
        elif order.signal.action == "EXIT":
             # Logic depends on current position side. Assuming Signal handles "SELL" to exit LONG.
             # If "EXIT" keyword is used, need logic to flatten.
             # Simplified: TREAT EXIT AS SELL for Longs.
             current_qty = self.positions.get(order.signal.symbol, 0)
             if current_qty > 0: # Long Exit
                 sale_qty = min(current_qty, qty) # Don't go short
                 proceeds = (price * sale_qty) - comm
                 self.cash += proceeds
                 self.positions[order.signal.symbol] -= sale_qty
             elif current_qty < 0: # Short Exit (Cover)
                 # Logic for short covering
                 pass
                 
        order.status = "FILLED"
        order.fill_price = price
        order.fill_time = timestamp
        
        self.trade_history.append({
            "id": order.order_id,
            "timestamp": timestamp,
            "symbol": order.signal.symbol,
            "action": order.signal.action,
            "qty": qty,
            "price": price,
            "comm": comm
        })
        
    def get_equity(self, current_prices: Dict[str, float]) -> float:
        """Calculate Total Equity (Cash + Open Positions)."""
        position_value = 0.0
        for sym, qty in self.positions.items():
            price = current_prices.get(sym, 0.0)
            position_value += (qty * price)
        return self.cash + position_value

import logging
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from core.config_manager import sys_config

class AccountingAgent(BaseAgent):
    def __init__(self):
        super().__init__("AccountingAgent")
        
        # Ledger 1: Paper Trading (₹1 Crore Mock)
        self.paper_ledger = {
            "balance": 10000000.0,
            "equity": 10000000.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0
        }
        
        # Ledger 2: Live Trading (Real Money)
        self.live_ledger = {
            "balance": 0.0, 
            "equity": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0
        }
        
        self.open_position = None  # {entry_price: float, qty: int}

    async def on_start(self):
        bus.subscribe(EventType.ORDER_EXECUTION, self.on_fill)
        bus.subscribe(EventType.MARKET_DATA, self.on_tick)

    async def on_stop(self):
        pass

    async def on_tick(self, tick: dict):
        # Select active ledger based on system mode
        ledger = self.paper_ledger if sys_config.MODE in ["PAPER", "BACKTEST"] else self.live_ledger
        
        # Update Unrealized P&L
        if self.open_position:
            current_price = tick['ltp']
            entry_price = self.open_position['entry_price']
            qty = self.open_position['qty']
            
            # Simple Long PnL: (Current - Entry) * Qty
            # In real system, handle Shorting too
            ledger["unrealized_pnl"] = (current_price - entry_price) * qty
        else:
            ledger["unrealized_pnl"] = 0.0
            
        ledger["equity"] = ledger["balance"] + ledger["unrealized_pnl"]

    async def on_fill(self, trade: dict):
        if trade['status'] != 'FILLED':
            return
            
        # Select active ledger
        ledger = self.paper_ledger if sys_config.MODE in ["PAPER", "BACKTEST"] else self.live_ledger

        price = trade['fill_price']
        qty = trade['quantity']
        action = trade['action']
        
        if self.open_position is None:
            if action == 'BUY':
                # OPENING NEW LONG TRADE
                self.open_position = {"entry_price": price, "qty": qty}
                self.logger.info(f"Position Opened: BUY {qty} @ {price}")
        else:
            if action == 'SELL':
                # CLOSING TRADE
                entry = self.open_position['entry_price']
                pnl = (price - entry) * qty
                
                ledger["balance"] += pnl
                ledger["realized_pnl"] += pnl
                ledger["trades"] += 1
                
                if pnl > 0:
                    ledger["wins"] += 1
                else:
                    ledger["losses"] += 1
                    
                self.logger.info(f"Position Closed: PnL ₹{pnl:.2f}")
                self.open_position = None
            
        # Recalc Win Rate
        if ledger["trades"] > 0:
            ledger["win_rate"] = round((ledger["wins"] / ledger["trades"]) * 100, 1)

    def get_finance_metrics(self):
        return {
            "paper": self.paper_ledger,
            "live": self.live_ledger
        }

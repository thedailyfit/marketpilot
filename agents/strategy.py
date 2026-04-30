import asyncio
import logging
from config import STOP_LOSS_PCT, TAKE_PROFIT_PCT

class StrategyAgent:
    def __init__(self, input_queue, execution_queue):
        self.input_queue = input_queue
        self.execution_queue = execution_queue
        self.price_history = [] 
        self.logger = logging.getLogger("Strategy")
        self.open_position = None # Track if we are in a trade

    async def start(self):
        self.logger.info("Velocity Scalper Strategy Started")
        asyncio.create_task(self._process_data())

    async def _process_data(self):
        while True:
            tick = await self.input_queue.get()
            current_price = tick['ltp']
            
            # --- 1. Manage OPEN Position (Risk & Exit) ---
            if self.open_position:
                entry_price = self.open_position['price']
                pnl_pct = (current_price - entry_price) / entry_price
                
                # Check Stop Loss (-5%)
                if pnl_pct <= -STOP_LOSS_PCT:
                     self.logger.warning(f"STOP LOSS HIT! P&L: {pnl_pct*100:.2f}%")
                     await self._send_exit_signal(current_price, "STOP_LOSS")
                
                # Check Take Profit (+5%)
                elif pnl_pct >= TAKE_PROFIT_PCT:
                    self.logger.info(f"TARGET HIT! P&L: {pnl_pct*100:.2f}%")
                    await self._send_exit_signal(current_price, "TAKE_PROFIT")
                
                # Simple Logging
                # else:
                #    self.logger.debug(f"Running P&L: {pnl_pct*100:.2f}%")

            # --- 2. Look for NEW Entries (Momentum) ---
            else:
                self.price_history.append(current_price)
                if len(self.price_history) > 20:
                    self.price_history.pop(0)
                    
                    # Simple Momentum Logic: Price > SMA(20) by 0.1% (Breakout)
                    avg_price = sum(self.price_history) / len(self.price_history)
                    if current_price > avg_price * 1.001: 
                        self.logger.info(f"Momentum Signal Detected! Price: {current_price}")
                        await self._send_entry_signal(current_price)

            self.input_queue.task_done()

    async def _send_entry_signal(self, price):
        signal = {
            "action": "BUY",
            "type": "ENTRY",
            "price": price
        }
        await self.execution_queue.put(signal)
        self.open_position = {"price": price, "start_time": asyncio.get_event_loop().time()}

    async def _send_exit_signal(self, price, reason):
        signal = {
            "action": "SELL",
            "type": "EXIT",
            "price": price,
            "reason": reason
        }
        await self.execution_queue.put(signal)
        self.open_position = None # Reset state

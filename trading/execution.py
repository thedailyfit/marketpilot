import asyncio
import logging
import random
import upstox_client
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from core.config_manager import sys_config

class ExecutionAgent(BaseAgent):
    def __init__(self):
        super().__init__("ExecutionAgent")
        self.upstox_user = None
        self.api_client = None
        
        # Paper Trading State
        self.paper_balance = 100000.0
        self.paper_pnl_realized = 0.0
        self.paper_pnl_unrealized = 0.0

        # Live State
        self.live_balance = 0.0
        self.live_pnl_realized = 0.0
        self.live_pnl_unrealized = 0.0

        # Trade History
        self.trade_history = []
        
        # Open Positions (for tracking entry/exit)
        self.open_positions = {}
        
        # Order ID counter
        self.order_counter = 1000

    async def on_start(self):
        # Subscribe to Validated Orders
        bus.subscribe(EventType.ORDER_VALIDATION, self.execute_order)
        bus.subscribe(EventType.MARKET_DATA, self.on_tick)
        bus.subscribe(EventType.TICK, self.on_tick)
        
        self.current_ltp = 150.0  # Default option price

        if sys_config.MODE == "LIVE":
            if sys_config.ACCESS_TOKEN:
                try:
                    conf = upstox_client.Configuration()
                    conf.access_token = sys_config.ACCESS_TOKEN
                    self.api_client = upstox_client.ApiClient(conf)
                    self.upstox_user = upstox_client.UserApi(self.api_client)
                    self.logger.info("Connected to Upstox API.")
                    await self.sync_funds()
                except Exception as e:
                    self.logger.error(f"Upstox Connection Failed: {e}")
            else:
                self.logger.warning("No ACCESS_TOKEN found. Live Execution disabled.")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        if isinstance(tick, dict):
            self.current_ltp = tick.get('ltp', self.current_ltp)
        
        # Check SL/TP for open positions
        await self._check_exit_conditions()

    async def execute_order(self, order_data):
        """Routes validated order to the appropriate venue."""
        self.logger.info(f"Received Validated Order: {order_data['action']} {order_data['quantity']} {order_data['symbol']}")
        
        if sys_config.MODE == "LIVE" and self.api_client:
            await self._execute_live(order_data)
        else:
            await self._execute_paper(order_data)

    async def _execute_paper(self, order):
        """Simulates realistic order execution with proper entry/exit tracking."""
        self.order_counter += 1
        order_id = f"ORD-{self.order_counter}"
        
        # REALISM UPGRADE: Wait 2 seconds to simulate network/exchange latency
        await asyncio.sleep(2.0)

        # Get realistic fill price
        base_price = order.get('price', 0.0)
        if base_price == 0:
            base_price = self.current_ltp
        
        # REALISM UPGRADE: Add Slippage (0.5% standard)
        # Market never fills us at perfect price.
        slippage_factor = 0.005 # 0.5%
        slippage = base_price * slippage_factor
        
        if order['action'] == 'BUY':
            fill_price = base_price + slippage  # Pay slightly more when buying
        else:
            fill_price = base_price - slippage  # Get slightly less when selling
        
        fill_price = round(fill_price, 2)
        
        # Log Slippage Impact
        self.logger.info(f"⏳ Latency: 2s | 📉 Slippage: ₹{slippage:.2f} (0.5%) | req: {base_price} -> fill: {fill_price}")
        
        # Calculate SL/TP levels
        sl_pct = order.get('sl_pct', 1.0)
        tp_pct = order.get('tp_pct', 2.0)
        quantity = order['quantity']
        
        if order['action'] == 'BUY':
            sl_price = round(fill_price * (1 - sl_pct / 100), 2)
            tp_price = round(fill_price * (1 + tp_pct / 100), 2)
        else:
            sl_price = round(fill_price * (1 + sl_pct / 100), 2)
            tp_price = round(fill_price * (1 - tp_pct / 100), 2)
        
        # Create timestamp
        now = datetime.now()
        timestamp = int(now.timestamp())  # Unix timestamp in seconds
        
        # Record entry trade
        entry_record = {
            "order_id": order_id,
            "status": "FILLED",
            "symbol": order['symbol'],
            "action": order['action'],
            "quantity": quantity,
            "entry_price": fill_price,
            "exit_price": 0.0,  # Not exited yet
            "sl_price": sl_price,
            "tp_price": tp_price,
            "timestamp": timestamp,
            "mode": "PAPER",
            "pnl": 0.0,  # Will be calculated on exit
            "strategy": order.get("strategy_id", "AI_SMART_EXEC"),
            "is_open": True
        }
        
        # Store in history
        self.trade_history.append(entry_record)
        
        # Track open position for SL/TP monitoring
        self.open_positions[order_id] = {
            "entry_price": fill_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "quantity": quantity,
            "action": order['action'],
            "symbol": order['symbol'],
            "strategy": order.get("strategy_id", "AI_SMART_EXEC"),
            "timestamp": timestamp,
            "history_index": len(self.trade_history) - 1,
            "trailed": False  # Track if SL has been trailed
        }
        
        self.logger.info(f"PAPER ENTRY: {order['action']} {quantity}x @ ₹{fill_price} | SL: ₹{sl_price} | TP: ₹{tp_price}")
        
        # Real-time tick monitoring handles exit now
        # Random simulation removed
        # asyncio.create_task(self._simulate_exit(order_id)) 
        
        await bus.publish(EventType.ORDER_EXECUTION, entry_record)

    async def _check_exit_conditions(self):
        """Check if any open positions hit SL or TP or Trail."""
        for order_id, position in list(self.open_positions.items()):
            ltp = self.current_ltp
            
            # Skip if symbol mismatch (simplified for single ticker focus)
            # In production, check tick.symbol == position['symbol']
            
            entry = position['entry_price']
            sl = position['sl_price']
            tp = position['tp_price']
            action = position['action']
            
            # --- SMART TRAIL LOGIC ---
            # If 50% of target reached, move SL to Breakeven
            if not position['trailed']:
                if action == 'BUY':
                    profit_pts = ltp - entry
                    target_pts = tp - entry
                    if profit_pts >= (target_pts * 0.5):
                        # Trail to Breakeven + small buffer
                        new_sl = entry + 1.0 
                        position['sl_price'] = new_sl
                        position['trailed'] = True
                        self.logger.info(f"🦅 SMART TRAIL: Moved SL to Breakeven @ {new_sl} for {order_id}")
                else: # SELL
                    profit_pts = entry - ltp
                    target_pts = entry - tp
                    if profit_pts >= (target_pts * 0.5):
                        new_sl = entry - 1.0
                        position['sl_price'] = new_sl
                        position['trailed'] = True
                        self.logger.info(f"🦅 SMART TRAIL: Moved SL to Breakeven @ {new_sl} for {order_id}")

            # --- EXIT CHECKS ---
            if action == 'BUY':
                if ltp >= tp:
                    await self._close_position(order_id, "TP", ltp)
                elif ltp <= sl:
                    await self._close_position(order_id, "SL", ltp)
            else:  # SELL
                if ltp <= tp:
                    await self._close_position(order_id, "TP", ltp)
                elif ltp >= sl:
                    await self._close_position(order_id, "SL", ltp)
    
    async def _close_position(self, order_id, exit_type, exit_price):
        """Close a position at specified price."""
        if order_id not in self.open_positions:
            return
            
        position = self.open_positions[order_id]
        entry_price = position['entry_price']
        quantity = position['quantity']
        action = position['action']
        
        if action == 'BUY':
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity
        
        pnl = round(pnl, 2)
        
        # Update trade record
        history_idx = position['history_index']
        if history_idx < len(self.trade_history):
            self.trade_history[history_idx]['exit_price'] = exit_price
            self.trade_history[history_idx]['pnl'] = pnl
            self.trade_history[history_idx]['is_open'] = False
        
        self.paper_pnl_realized += pnl
        del self.open_positions[order_id]
        
        self.logger.info(f"{'✅' if exit_type == 'TP' else '❌'} {exit_type} HIT: Exit @ ₹{exit_price} | P&L: ₹{pnl}")
    
    @property
    def daily_pnl(self):
        """Returns total daily P&L."""
        return self.paper_pnl_realized + self.paper_pnl_unrealized

    async def _execute_live(self, order):
        """Places real order via Upstox API."""
        self.logger.info("Placing LIVE Order (Upstox)...")
        if not self.api_client:
            self.logger.error("API Client not initialized.")
            return

        try:
            instrument_token = order['symbol']
            qty = order['quantity']
            transaction_type = order['action']
            order_type = "MARKET" if order.get('price', 0) == 0 else "LIMIT"
            product = "I"
            
            api_instance = upstox_client.OrderApi(self.api_client)
            
            body = upstox_client.PlaceOrderRequest(
                quantity=qty,
                product=product,
                validity="DAY",
                price=order.get('price', 0.0),
                tag="MARKETPILOT",
                instrument_token=instrument_token,
                order_type=order_type,
                transaction_type=transaction_type,
                disclosed_quantity=0,
                trigger_price=0.0,
                is_amo=False
            )
            
            self.logger.info(f"Sending Order Body: {body}")
            api_response = api_instance.place_order(body, "2.0")
            self.logger.info(f"Live Order Response: {api_response}")
            
            self.order_counter += 1
            result = {
                "order_id": api_response.data.order_id if hasattr(api_response, 'data') else f"ORD-{self.order_counter}",
                "status": "SUBMITTED",
                "symbol": order['symbol'],
                "action": order['action'],
                "quantity": qty,
                "entry_price": order.get('price', 0.0),
                "exit_price": 0.0,
                "timestamp": int(datetime.now().timestamp()),
                "mode": "LIVE",
                "pnl": 0.0,
                "strategy": order.get("strategy_id", "MANUAL")
            }
            
            self.trade_history.append(result)
            await bus.publish(EventType.ORDER_EXECUTION, result)
            
        except Exception as e:
            self.logger.error(f"Live Order Placement Failed: {e}")

    async def sync_funds(self):
        """Fetches real funds from Upstox."""
        if not self.upstox_user:
            return
        try:
            api_response = self.upstox_user.get_user_fund_margin("2.0", segment="SEC")
            data = api_response.data
            if data:
                self.live_balance = data.equity.available_margin if hasattr(data, 'equity') else 0.0
            self.logger.info(f"Live Funds Fetched: ₹{self.live_balance}")
        except Exception as e:
            self.logger.error(f"Failed to sync funds: {e}")

    def get_live_balance(self):
        return self.live_balance

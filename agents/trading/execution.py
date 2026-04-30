import asyncio
import logging
import random
import upstox_client
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from core.config_manager import sys_config

# LEVEL-06: Single ExecutionGateway (replaces scattered gates)
from core.gateway import execution_gateway, RiskDecision

# Legacy imports kept for theta/vega booking only
from core.governor import frequency_regulator
from core.risk import theta_budget_manager, vega_exposure_limit, loss_streak_dampener


from core.execution import (
    smart_order_engine, 
    execution_quality_monitor,
    Urgency,
    ExecutionRequest
)

# LEVEL-14: Zone-Aware Risk Placement
from core.volume import volume_risk_engine

# LEVEL-15: Multi-Leg Execution
from core.execution import leg_risk_simulator
from core.options.chain_snapshot import OptionSnapshot

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
        """
        Routes validated order to the appropriate venue.
        
        LEVEL-06: All orders MUST pass through ExecutionGateway.
        No order reaches broker API without gateway approval.
        
        The gateway validates against ALL risk engines:
        1. Regime constraints (PANIC mode restrictions)
        2. Drawdown limits (daily/weekly)
        3. Trading Governor (noise, confidence, timing)
        4. Frequency limits (trades per day)
        5. Theta budget
        6. Vega limits
        7. Loss streak adjustment
        """
        self.logger.info(f"🔒 GATEWAY: Received order {order_data['action']} {order_data['quantity']}x {order_data['symbol']}")
        
        # ============== SINGLE GATEWAY VALIDATION ==============
        decision = execution_gateway.validate(order_data)
        
        if decision.action == "BLOCK":
            self.logger.warning(f"🚫 GATEWAY BLOCKED: {decision.reason}")
            await self._emit_block_event(order_data, decision.reason, decision.restrictions)
            return {
                "status": "BLOCKED",
                "reason": decision.reason,
                "gate_results": decision.gate_results
            }
        
        # ============== GATEWAY APPROVED ==============
        # Apply size modifier from gateway
        original_qty = order_data['quantity']
        adjusted_qty = max(1, int(original_qty * decision.size_multiplier))
        
        if adjusted_qty != original_qty:
            order_data['quantity'] = adjusted_qty
            self.logger.info(f"📉 SIZE ADJUSTED: {original_qty} → {adjusted_qty} ({decision.size_multiplier:.0%})")
        
        self.logger.info(f"✅ GATEWAY APPROVED: Executing {order_data['action']} {adjusted_qty}x {order_data['symbol']}")
        
        # Record trade for frequency tracking
        trade_id = f"ORD-{self.order_counter + 1}"
        frequency_regulator.record_trade(
            trade_id=trade_id,
            symbol=order_data['symbol'],
            side=order_data['action']
        )
        
        # Book theta/vega exposure
        order_theta = order_data.get("theta", 0)
        order_vega = order_data.get("vega", 0)
        
        if order_theta > 0:
            estimated_theta = abs(order_theta) * adjusted_qty
            theta_budget_manager.update_current_theta(
                theta_budget_manager.current_theta + estimated_theta
            )
        
        if order_vega > 0:
            estimated_vega = abs(order_vega) * adjusted_qty
            vega_exposure_limit.update_current_vega(
                vega_exposure_limit.current_vega + estimated_vega
            )
        
        # Execute via appropriate venue
        if sys_config.MODE == "LIVE" and self.api_client:
            # SAFETY: Block Multi-Leg in Live until Atomic Execution supported
            if "legs" in order_data and order_data["legs"]:
                 self.logger.warning("🚫 LIVE Multi-Leg Execution BLOCKED (Atomic execution required)")
                 return {"status": "BLOCKED", "reason": "Live Multi-Leg Not Implemented"}
            
            result = await self._execute_live(order_data)
        else:
            # Handle Multi-Leg Execution
            if "legs" in order_data and order_data["legs"]:
                result = await self._execute_spread_paper(order_data)
            else:
                result = await self._execute_paper(order_data)
        
        return result

    async def _execute_spread_paper(self, order_data: dict):
        """
        Executes a multi-leg strategy (Spread) in paper mode.
        Validates legging risk before proceeding.
        """
        # 1. Validate Legging Risk
        legs = order_data["legs"]
        if len(legs) >= 2:
            # Reconstruct OptionSnapshots approx (for simulation)
            # Assuming legs have necessary data
            long_leg_data = legs[0] if legs[0]["action"] == "BUY" else legs[1]
            short_leg_data = legs[1] if legs[1]["action"] == "SELL" else legs[0]
            
            # Create dummy snapshots for risk check
            # We need minimal fields: ltp, ask, bid, oi
            long_snap = OptionSnapshot(
                symbol=long_leg_data["symbol"], strike=0, expiry="", option_type="",
                ltp=long_leg_data.get("ltp", 100), bid=0, ask=long_leg_data.get("ltp", 100),
                oi=10000, volume=1000, iv=0, delta=0, gamma=0, theta=0, vega=0, timestamp=0
            )
            short_snap = OptionSnapshot(
                symbol=short_leg_data["symbol"], strike=0, expiry="", option_type="",
                ltp=short_leg_data.get("ltp", 80), bid=short_leg_data.get("ltp", 80), ask=0,
                oi=short_leg_data.get("oi", 5000), volume=1000, iv=0, delta=0, gamma=0, theta=0, vega=0, timestamp=0
            )
            
            risk_budget = order_data.get("risk_budget", 5000.0)
            
            risk_report = leg_risk_simulator.assess_legging_risk(
                long_leg=long_snap,
                short_leg=short_snap,
                max_risk_budget=risk_budget
            )
            
            if not risk_report.is_safe:
                self.logger.warning(f"🚫 LEG RISK BLOCKED: {risk_report.reason}")
                return {
                    "status": "BLOCKED",
                    "reason": risk_report.reason,
                    "risk_report": risk_report
                }
                
            self.logger.info(f"✅ Leg Risk Safe: Slippage est. {risk_report.estimated_slippage:.2f}")

        # 2. Execute Legs Sequentially
        fill_results = []
        for leg in legs:
            # Execute each leg
            # Inherit parent urgency? Or specific?
            leg_order = leg.copy()
            leg_order["urgency"] = order_data.get("urgency", "BALANCED")
            
            # Simple simulation call
            fill = await self._execute_paper(leg_order)
            fill_results.append(fill)
            
            # Minimal delay between legs
            await asyncio.sleep(0.5)
            
        return {
            "status": "FILLED",
            "legs": fill_results,
            "strategy": order_data.get("strategy", "VERTICAL_SPREAD")
        }

    async def _emit_block_event(self, order_data: dict, reason: str, restrictions: list):
        """Emit a block event for audit trail."""
        block_event = {
            "type": "ORDER_BLOCKED",
            "order": order_data,
            "reason": reason,
            "restrictions": restrictions,
            "timestamp": int(datetime.now().timestamp())
        }
        await bus.publish(EventType.TRADE_BLOCKED, block_event)
        self.logger.warning(f"📋 Block event emitted: {reason}")




    async def _execute_paper(self, order):
        """Simulates realistic order execution with proper entry/exit tracking."""
        self.order_counter += 1
        order_id = f"ORD-{self.order_counter}"
        
        # LEVEL-09: Smart Execution Logic
        # 1. Determine Urgency
        urgency_str = order.get('urgency', 'BALANCED')
        try:
            urgency = Urgency[urgency_str]
        except:
            urgency = Urgency.BALANCED
            
        # 2. Simulate Depth Data (for logic testing)
        # In real live trading, this comes from market data
        current_ltp = self.current_ltp
        spread = current_ltp * 0.005 # 0.5% spread
        market_data = {
            "ltp": current_ltp,
            "bid": current_ltp - (spread/2),
            "ask": current_ltp + (spread/2),
            "spread": spread
        }
        
        # 3. Get Smart Placement Params
        exec_req = ExecutionRequest(
            symbol=order['symbol'],
            action=order['action'],
            quantity=order['quantity'],
            urgency=urgency,
            limit_price=order.get('limit_price', 0.0)
        )
        
        params = smart_order_engine.get_placement_params(exec_req, market_data)
        target_price = params['price']
        
        # REALISM UPGRADE: Wait 2 seconds to simulate network/exchange latency
        await asyncio.sleep(2.0)

        # Get realistic fill price based on Urgency
        # Passive: Gets Limit Price (if filled)
        # Aggressive: Pays Spread + Slippage
        
        if urgency == Urgency.PASSIVE:
            # 50% chance of fill at limit price
            filled = random.random() > 0.5
            if not filled:
                # Move to Balanced (simulate timeout logic)
                target_price = market_data['ltp'] # Midpt
                
        # Calculate final fill price with minimal noise
        base_fill = target_price if target_price > 0 else current_ltp
        noise = random.uniform(-0.05, 0.05) # Tick noise
        fill_price = round(base_fill + noise, 2)
        
        # Log Execution Quality
        expected_price = market_data['ask'] if order['action'] == 'BUY' else market_data['bid']
        execution_quality_monitor.record_execution(
            symbol=order['symbol'],
            action=order['action'],
            expected_price=expected_price,
            fill_price=fill_price,
            urgency=urgency.name
        )
        
        # Calculate SL/TP levels
        # LEVEL-14: Zone-Aware Risk Placement
        # Try to get zone-aware stops first, fallback to percentage
        direction = "LONG" if order['action'] == 'BUY' else "SHORT"
        risk_placement = volume_risk_engine.calculate(
            direction=direction,
            entry_price=fill_price
        )
        
        if risk_placement.is_valid:
            sl_price = risk_placement.stop_loss
            tp_price = risk_placement.take_profit
            self.logger.info(f"🎯 ZONE-AWARE SL/TP: {risk_placement.reasoning}")
        else:
            # Fallback to percentage-based (legacy)
            self.logger.warning(f"⚠️ Zone placement unavailable: {risk_placement.rejection_reason}")
            sl_pct = order.get('sl_pct', 1.0)
            tp_pct = order.get('tp_pct', 2.0)
            
            if order['action'] == 'BUY':
                sl_price = round(fill_price * (1 - sl_pct / 100), 2)
                tp_price = round(fill_price * (1 + tp_pct / 100), 2)
            else:
                sl_price = round(fill_price * (1 + sl_pct / 100), 2)
                tp_price = round(fill_price * (1 - tp_pct / 100), 2)
        
        quantity = order['quantity']
        
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
            "urgency": urgency.name,
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
        
        self.logger.info(f"PAPER ENTRY: {order['action']} {quantity}x @ ₹{fill_price} [{urgency.name}] | SL: ₹{sl_price} | TP: ₹{tp_price}")
        
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
        
        # ============== OUTCOME RECORDING ==============
        # Record to ExecutionGateway (for drawdown tracking)
        execution_gateway.record_outcome(pnl)
        
        # Record outcome for LossStreakDampener
        loss_streak_dampener.record_result(
            trade_id=order_id,
            symbol=position.get('symbol', 'UNKNOWN'),
            pnl=pnl
        )
        
        # Note: Theta/Vega will be naturally released at EOD when positions reset
        
        is_win = pnl > 0
        self.logger.info(f"{'✅' if exit_type == 'TP' else '❌'} {exit_type} HIT: Exit @ ₹{exit_price} | P&L: ₹{pnl}")
        status = loss_streak_dampener.get_status()
        self.logger.info(f"📊 Outcome: {'WIN' if is_win else 'LOSS'} | Streak: {status.consecutive_losses} losses | Size: {status.size_multiplier:.0%}")


    
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
            
            # LEVEL-09: Smart Order Params
            # Use market data (if available) to set better limits
            urgency_str = order.get('urgency', 'BALANCED')
            try:
                urgency = Urgency[urgency_str]
            except:
                urgency = Urgency.BALANCED
                
            limit_price = order.get('price', 0.0) # From signal or manual override
            
            # Fetch live market depth for smart execution
            if sys_config.MODE == "LIVE" and self.api_client:
                try:
                    quote_api = upstox_client.MarketQuoteApi(self.api_client)
                    quote_resp = quote_api.get_full_market_quote(symbol=instrument_token, api_version="2.0")
                    
                    if quote_resp.data and instrument_token in quote_resp.data:
                        market_data = quote_resp.data[instrument_token]
                        depth = market_data.depth
                        
                        best_bid = depth.buy[0].price if depth.buy and depth.buy[0].price else market_data.last_price
                        best_ask = depth.sell[0].price if depth.sell and depth.sell[0].price else market_data.last_price
                        
                        if transaction_type == "BUY":
                            if urgency == Urgency.AGGRESSIVE:
                                limit_price = best_ask + 0.10 # Hit ask + slip
                            elif urgency == Urgency.BALANCED:
                                limit_price = (best_bid + best_ask) / 2 # Midpoint
                            else: # PASSIVE
                                limit_price = best_bid # Sit on bid
                        else: # SELL
                            if urgency == Urgency.AGGRESSIVE:
                                limit_price = best_bid - 0.10 # Hit bid - slip
                            elif urgency == Urgency.BALANCED:
                                limit_price = (best_bid + best_ask) / 2 # Midpoint
                            else: # PASSIVE
                                limit_price = best_ask # Sit on ask
                                
                        # Round to tick size 0.05
                        limit_price = round(limit_price * 20) / 20.0
                except Exception as e:
                    self.logger.warning(f"Failed to fetch L2 Market Depth for {instrument_token}: {e}")
            
            order_type = "MARKET" if limit_price == 0 else "LIMIT"
            product = "I"
            
            api_instance = upstox_client.OrderApi(self.api_client)
            
            body = upstox_client.PlaceOrderRequest(
                quantity=qty,
                product=product,
                validity="DAY",
                price=limit_price,
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
                "entry_price": limit_price,
                "exit_price": 0.0,
                "timestamp": int(datetime.now().timestamp()),
                "mode": "LIVE",
                "pnl": 0.0,
                "strategy": order.get("strategy_id", "MANUAL"),
                "urgency": urgency.name
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

    @property
    def paper_mode(self):
        return sys_config.MODE != "LIVE"

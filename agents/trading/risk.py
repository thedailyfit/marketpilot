"""
Enhanced Risk Agent
Provides comprehensive risk management including position sizing, 
drawdown control, and integration with PositionManager.
"""
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from core.config_manager import sys_config
from core.risk_calculator import calculate_risk_levels, calculate_atr
from agents.trading.position_manager import PositionManager


class RiskAgent(BaseAgent):
    def __init__(self):
        super().__init__("RiskAgent")
        
        # Risk Parameters
        self.max_daily_loss = getattr(sys_config, 'MAX_DAILY_LOSS', 2000.0)
        self.max_risk_per_trade = 1.0  # 1% of account per trade
        self.is_paused = False
        self.current_vix = 15.0
        
        # Position Manager reference (set by Supervisor)
        self.position_manager: PositionManager = None
        
        # Recent candles for ATR (shared via subscription)
        self.recent_candles = {}

    async def on_start(self):
        bus.subscribe(EventType.SIGNAL, self.validate_signal)
        bus.subscribe(EventType.ORDER_EXECUTION, self.on_execution)
        bus.subscribe(EventType.CANDLE_DATA, self.on_candle)
        bus.subscribe(EventType.ANALYSIS, self.on_analysis) # Ensure subscription to ANALYSIS event
        
        # Initialize daily balance
        self.daily_starting_balance = 100000.0  # Will be synced from ExecutionAgent
        self.logger.info(f"RiskAgent started. Max Loss: ₹{self.max_daily_loss} | Risk/Trade: {self.max_risk_per_trade}%")

    async def on_stop(self):
        pass
    
    def set_position_manager(self, pm: PositionManager):
        """Set reference to PositionManager."""
        self.position_manager = pm
    
    async def on_candle(self, candle: dict):
        """Store candles for ATR calculation."""
        symbol = candle.get('symbol')
        if not symbol:
            return
        
        if symbol not in self.recent_candles:
            self.recent_candles[symbol] = []
        
        self.recent_candles[symbol].append(candle)
        self.recent_candles[symbol] = self.recent_candles[symbol][-20:]

    async def on_execution(self, execution: dict):
        """Track P&L from executions."""
        pnl = execution.get('pnl', 0.0)
        if pnl < 0:
            self.daily_loss += abs(pnl)
            prev_losses = getattr(self, 'consecutive_losses', 0)
            self.consecutive_losses = prev_losses + 1
        else:
            self.consecutive_losses = 0
            
        self.trades_today += 1
        
        # Check drawdown
        drawdown_percent = (self.daily_loss / self.daily_starting_balance) * 100
        if drawdown_percent >= self.drawdown_pause_threshold:
            self.is_paused = True
            self.logger.warning(f"⚠️ TRADING PAUSED: Drawdown {drawdown_percent:.1f}% hit threshold.")


    async def on_analysis(self, analysis: dict):
        """Listen for sentiment/VIX updates."""
        if analysis.get('type') == 'SENTIMENT_UPDATE':
            data = analysis.get('data', {})
            self.current_vix = data.get('vix', 15.0)

    async def validate_signal(self, signal):
        """Comprehensive signal validation with position sizing."""
        symbol = signal.get('symbol', 'UNKNOWN')
        direction = signal.get('signal_type', 'BUY')
        
        # === RISK CHECKS ===
        
        # 1. Check if trading is paused
        if self.is_paused:
            self.logger.warning(f"Signal REJECTED: Trading paused due to drawdown.")
            return
        
        # 2. Check Max Daily Loss (hard limit)
        if self.daily_loss >= self.max_daily_loss:
            self.logger.warning(f"Signal REJECTED: Max daily loss (₹{self.max_daily_loss}) reached.")
            return
        
        # 3. Check concurrent positions
        if self.position_manager:
            if not self.position_manager.can_open_position():
                self.logger.warning(f"Signal REJECTED: Max concurrent positions reached.")
                return
            
            # Check if already in position for this symbol
            existing = self.position_manager.get_position(symbol)
            if existing and existing.status == "OPEN":
                self.logger.warning(f"Signal REJECTED: Already in position for {symbol}.")
                return
        
        # 4. Time-based filter (don't trade in last 30 mins)
        now = datetime.now()
        if now.hour == 15 and now.minute >= 0:
            self.logger.warning(f"Signal REJECTED: Too close to market close.")
            return

        # 5. IV CRUSH GUARD (PRICE POLICE)
        # Check if VIX is too high (IV > 90th percentile proxy)
        # If High IV -> Block Naked Buys to prevent "Crush"
        iv_limit_high = 24.0 # VIX level considered "Extreme"
        strategy = signal.get('strategy_id', 'UNKNOWN')

        if self.current_vix > iv_limit_high and strategy != "GammaBlast": # GammaBlast allowed
            self.logger.warning(f"🚫 BLOCKED: IV GUARD triggered (VIX {self.current_vix} > {iv_limit_high})")
            return
            
        # 6. GLOBAL TETHER (MACRO VETO)
        # Check USDINR Correlation
        from agents.ops.supervisor import supervisor
        if hasattr(supervisor, 'macro_agent'):
             is_vetoed, reason = supervisor.macro_agent.check_veto(direction)
             if is_vetoed:
                 self.logger.warning(f"🚫 BLOCKED: MACRO VETO ({reason})")
                 return
                 
        # 7. GRANDMASTER DEFENSE (SECTOR & GAP & ZEN)
        # Check Sector Consensus
        if hasattr(supervisor, 'sector_agent'):
             is_aligned, reason = supervisor.sector_agent.check_alignment(direction)
             if not is_aligned:
                 self.logger.warning(f"🚫 BLOCKED: SECTOR MISMATCH ({reason})")
                 return
                 
        # Check Gap No Fly Zone
        if hasattr(supervisor, 'gap_agent'):
             entry_price_check = 0 # Market price
             is_blocked, reason = supervisor.gap_agent.check_zone(entry_price_check)
             if is_blocked:
                 self.logger.warning(f"🚫 BLOCKED: GAP ZONE ({reason})")
                 return
                 
        # Check Zen Master (3-Strike Rule)
        # Assuming we track consecutive losses in self.consecutive_losses
        if getattr(self, 'consecutive_losses', 0) >= 3:
             self.logger.warning(f"🚫 BLOCKED: ZEN MASTER (3 Consecutive Losses - Cool Down)")
             return
             
        # 8. APEX MIND (CONSENSUS SCORE)
        # Calculate Confidence Score (0-10)
        score = 5 # Base score
        
        # Oracle Boost
        if hasattr(supervisor, 'fractal_agent') and supervisor.fractal_agent.royal_flush_active:
            score += 2
        
        # Predator Boost
        if hasattr(supervisor, 'trap_agent') and getattr(supervisor.trap_agent, 'is_below_support', False) == False: # Reclaimed
            score += 2
            
        # Grandmaster Boost
        if hasattr(supervisor, 'sector_agent') and "BULLISH" in getattr(supervisor.sector_agent, 'consensus_status', ''):
            if direction == 'BUY': score += 1
            
        # Whale Boost
        if hasattr(supervisor, 'whale_agent') and getattr(supervisor.whale_agent, 'sonar_status', '') == "ACCUMULATION_DETECTED":
            score += 2
            
        # Score Logic
        if score < 4:
            self.logger.warning(f"🚫 BLOCKED: LOW CONFIDENCE SCORE ({score}/10)")
            return
            
        # Start Sizing
        if signal['quantity'] == 0:
            return
            
        # 9. MATRIX ARCHITECT VETOES (FII & PREMIUM)
        # Check FII Tracker (OI Power)
        if hasattr(supervisor, 'fii_tracker'):
             is_valid, reason = supervisor.fii_tracker.check_trend_validity(direction)
             if not is_valid:
                 self.logger.warning(f"🚫 BLOCKED: FII VETO ({reason})")
                 return
                 
        # Check Premium Lab (Divergence)
        if hasattr(supervisor, 'premium_lab'):
             is_healthy, reason = supervisor.premium_lab.check_premium_health()
             if not is_healthy:
                 self.logger.warning(f"🚫 BLOCKED: PREMIUM VETO ({reason})")
                 return
                 
        # 10. NEURAL SENTRY (CONVICTION BOOSTER)
        if hasattr(supervisor, 'neural_sentry'):
             # Create current state snapshot for matching
             current_state = {
                 "trinity": "BULLISH" if direction == 'BUY' else "BEARISH",
                 # ... more features
             }
             is_match, confidence = supervisor.neural_sentry.check_pattern_match(current_state)
             if is_match:
                 self.logger.info(f"🧠 NEURAL SENTRY: Pattern MATCH ({int(confidence*100)}%)! Conventional Risk Relaxed.")
                 # Logic to relax risk or boost size could go here

        # 11. GALAXY CORE VETOES (GLOBAL SENTIMENT & CORRELATION)
        # Check Sentiment Harvester
        if hasattr(supervisor, 'sentiment_agent'):
             is_veto, reason = supervisor.sentiment_agent.check_veto()
             if is_veto:
                 self.logger.warning(f"🚫 BLOCKED: SENTIMENT VETO ({reason})")
                 return
                 
        # Check Global Correlation Matrix
        if hasattr(supervisor, 'correlation_agent'):
             is_veto, reason = supervisor.correlation_agent.check_correlation_veto(direction)
             if is_veto:
                 self.logger.warning(f"🚫 BLOCKED: GLOBAL CORRELATION VETO ({reason})")
                 return
                 
        # 12. ALPHA ALCHEMIST (STRATEGY CONFIG)
        if hasattr(supervisor, 'optimizer_agent'):
             supervisor.optimizer_agent.run_optimization(self.current_vix)
             
        # 13. SHADOW PROTOCOL (BLOCK DEALS & TAPE PRESSURE)
        # Check Block Deal Sniper
        if hasattr(supervisor, 'block_sniper'):
             interest = supervisor.block_sniper.get_whale_flag()
             if direction == "BUY" and interest == "DISTRIBUTION":
                 self.logger.warning("🚫 BLOCKED: SHADOW VETO (Institutional Distribution Detected)")
                 return
             if direction == "SELL" and interest == "HIGH_ACCUMULATION":
                 self.logger.warning("🚫 BLOCKED: SHADOW VETO (Institutional Accumulation Detected)")
                 return

        # Check Tape Master (OBI)
        if hasattr(supervisor, 'tape_master'):
             state = supervisor.tape_master.market_state
             if direction == "BUY" and state == "SELL_PRESSURE":
                 self.logger.warning("🚫 BLOCKED: TAPE VETO (Heavy Sell Pressure on Order Book)")
                 return
             if direction == "SELL" and state == "BUY_PRESSURE":
                 self.logger.warning("🚫 BLOCKED: TAPE VETO (Heavy Buy Pressure on Order Book)")
                 return
        
        # 14. THE FLOW STATE (GOD MODE SIZING)
        size_multiplier = 1.0
        if hasattr(supervisor, 'flow_agent') and supervisor.flow_agent.is_god_mode:
             self.logger.warning("💎 GOD MODE ACTIVE: Position Size Multiplied x3")
             size_multiplier = 3.0
             
        # === GAMMA SCALING (VIX BASED) ===
        vix = self.current_vix # Use subscribed VIX
            
        gamma_multiplier = 1.0
        sl_multiplier = 1.0
        
        if vix < 12: 
            gamma_multiplier = 1.2 # Aggressive
            self.logger.info(f"💎 Low VIX ({vix}): Gamma Scaling applied (1.2x Lots)")
        elif vix > 20:
            gamma_multiplier = 0.25 # Defensive
            sl_multiplier = 1.3     # 30% wider SL for volatility
            self.logger.info(f"🛡️ High VIX ({vix}): Gamma Scaling applied (0.25x Lots + Wider SL)")
        elif vix > 16:
            gamma_multiplier = 0.5
            self.logger.info(f"⚠️ Elevated VIX ({vix}): Gamma Scaling applied (0.5x Lots)")

        # Calculate risk levels
        account_balance = self.daily_starting_balance - self.daily_loss
        
        # Use risk calculator
        risk_levels = calculate_risk_levels(
            entry_price=entry_price,
            candles=candles,
            direction=direction,
            account_balance=account_balance,
            risk_percent=self.max_risk_per_trade,
            atr_multiplier=1.5 * sl_multiplier,
            rr_ratio=2.0,
            lot_size=1
        )
        
        # Apply Gamma Multiplier to final position size
        final_qty = max(1, int(risk_levels.position_size * gamma_multiplier))
        
        self.logger.info(f"Risk Check PASSED. Gamma Scaled Qty: {final_qty} (Orig: {risk_levels.position_size}) | SL: {risk_levels.stop_loss}")
        
        # === PREPARE ORDER ===
        order = {
            "symbol": symbol,
            "action": direction,
            "quantity": final_qty,
            "price": 0.0,  # Market order
            "type": "MARKET",
            "stop_loss": risk_levels.stop_loss,
            "take_profit": risk_levels.take_profit,
            "strategy_id": signal.get('strategy_id', 'UNKNOWN')
        }

        # 15. ZENITH SNIPER (DECISION MAKER - SMART EXECUTE)
        # Instead of direct execute, we pass to Zenith for optimal entry
        if hasattr(supervisor, 'decision_maker'):
             self.logger.info("🧠 ZENITH SNIPER INTERCEPTED: Waiting for optimal pullback/entry...")
             supervisor.decision_maker.intercept_and_wait(order)
             return # Zenith will publish SMART_EXECUTE when ready

        # Fallback to direct execute if DecisionMaker is missing
        if self.position_manager:
            await self.position_manager.open_position(
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                quantity=final_qty,
                stop_loss=risk_levels.stop_loss,
                take_profit=risk_levels.take_profit
            )
        
        await bus.publish(EventType.ORDER_VALIDATION, order)
    
    def reset_daily(self):
        """Reset daily counters (call at start of each trading day)."""
        self.daily_loss = 0.0
        self.trades_today = 0
        self.is_paused = False
        self.logger.info("Daily risk counters reset.")
    
    def get_risk_status(self) -> dict:
        """Get current risk status."""
        remaining_loss = self.max_daily_loss - self.daily_loss
        drawdown = (self.daily_loss / self.daily_starting_balance) * 100 if self.daily_starting_balance > 0 else 0
        
        return {
            "daily_loss": round(self.daily_loss, 2),
            "remaining_capacity": round(remaining_loss, 2),
            "drawdown_percent": round(drawdown, 2),
            "trades_today": self.trades_today,
            "is_paused": self.is_paused,
            "max_risk_per_trade": f"{self.max_risk_per_trade}%"
        }

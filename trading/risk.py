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
        self.max_concurrent_positions = 3
        self.drawdown_pause_threshold = 5.0  # Pause at -5% daily
        
        # State
        self.daily_loss = 0.0
        self.daily_starting_balance = 0.0
        self.trades_today = 0
        self.is_paused = False
        
        # Position Manager reference (set by Supervisor)
        self.position_manager: PositionManager = None
        
        # Recent candles for ATR (shared via subscription)
        self.recent_candles = {}

    async def on_start(self):
        bus.subscribe(EventType.SIGNAL, self.validate_signal)
        bus.subscribe(EventType.ORDER_EXECUTION, self.on_execution)
        bus.subscribe(EventType.CANDLE_DATA, self.on_candle)
        
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
            
        self.trades_today += 1
        
        # Check drawdown
        drawdown_percent = (self.daily_loss / self.daily_starting_balance) * 100
        if drawdown_percent >= self.drawdown_pause_threshold:
            self.is_paused = True
            self.logger.warning(f"⚠️ TRADING PAUSED: Drawdown {drawdown_percent:.1f}% hit threshold.")

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
        
        # === POSITION SIZING ===
        
        # Get current price (from signal or default)
        entry_price = signal.get('price', 0.0)
        if entry_price == 0:
            entry_price = 19500.0  # Fallback, should come from market data
        
        # Get candles for ATR
        candles = self.recent_candles.get(symbol, [])
        
        # Calculate risk levels
        account_balance = self.daily_starting_balance - self.daily_loss
        
        # Use risk calculator
        risk_levels = calculate_risk_levels(
            entry_price=entry_price,
            candles=candles,
            direction=direction,
            account_balance=account_balance,
            risk_percent=self.max_risk_per_trade,
            atr_multiplier=1.5,
            rr_ratio=2.0,
            lot_size=1
        )
        
        self.logger.info(f"Risk Check PASSED. Position Size: {risk_levels.position_size} | SL: {risk_levels.stop_loss} | TP: {risk_levels.take_profit}")
        
        # === OPEN POSITION ===
        
        if self.position_manager:
            await self.position_manager.open_position(
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                quantity=risk_levels.position_size,
                stop_loss=risk_levels.stop_loss,
                take_profit=risk_levels.take_profit
            )
        
        # === PUBLISH ORDER ===
        
        order = {
            "symbol": symbol,
            "action": direction,
            "quantity": risk_levels.position_size,
            "price": 0.0,  # Market order
            "type": "MARKET",
            "stop_loss": risk_levels.stop_loss,
            "take_profit": risk_levels.take_profit,
            "strategy_id": signal.get('strategy_id', 'UNKNOWN')
        }
        
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

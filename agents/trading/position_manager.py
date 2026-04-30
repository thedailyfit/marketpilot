"""
Position Manager
Tracks open positions and manages exits (SL, TP, Trailing, EOD).
"""
import asyncio
import logging
from datetime import datetime, time
from typing import Dict, Optional, List
from dataclasses import dataclass, field, asdict
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from core.risk_calculator import calculate_trailing_stop, calculate_atr


@dataclass
class Position:
    symbol: str
    direction: str  # BUY or SELL
    entry_price: float
    quantity: int
    stop_loss: float
    take_profit: float
    entry_time: float
    current_stop: float = field(default=0.0)
    highest_price: float = field(default=0.0)  # For trailing
    lowest_price: float = field(default=0.0)   # For trailing
    pnl: float = field(default=0.0)
    status: str = field(default="OPEN")  # OPEN, CLOSED, SL_HIT, TP_HIT, EOD_EXIT
    
    def __post_init__(self):
        if self.current_stop == 0.0:
            self.current_stop = self.stop_loss
        if self.highest_price == 0.0:
            self.highest_price = self.entry_price
        if self.lowest_price == 0.0:
            self.lowest_price = self.entry_price


class PositionManager(BaseAgent):
    """Manages open positions with SL/TP/Trailing monitoring."""
    
    def __init__(self):
        super().__init__("PositionManager")
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        self.closed_positions: List[Position] = []
        self.max_concurrent: int = 3
        self.eod_close_time: time = time(15, 25)  # 3:25 PM IST
        self.trailing_enabled: bool = True
        self.recent_candles: Dict[str, List[dict]] = {}  # For ATR calc
        
    async def on_start(self):
        # Subscribe to market data for SL/TP monitoring
        bus.subscribe(EventType.MARKET_DATA, self.on_tick)
        bus.subscribe(EventType.CANDLE_DATA, self.on_candle)
        bus.subscribe(EventType.ORDER_EXECUTION, self.on_order_filled)
        
        # Start EOD monitor
        asyncio.create_task(self._eod_monitor())
        self.logger.info("PositionManager started. Monitoring SL/TP/Trailing.")
        
    async def on_stop(self):
        pass
    
    def can_open_position(self) -> bool:
        """Check if we can open a new position."""
        open_count = len([p for p in self.positions.values() if p.status == "OPEN"])
        return open_count < self.max_concurrent
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get open position for symbol."""
        return self.positions.get(symbol)
    
    def get_all_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [p for p in self.positions.values() if p.status == "OPEN"]
    
    async def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: int,
        stop_loss: float,
        take_profit: float
    ) -> Optional[Position]:
        """Open a new position."""
        if not self.can_open_position():
            self.logger.warning(f"Max concurrent positions ({self.max_concurrent}) reached.")
            return None
        
        if symbol in self.positions and self.positions[symbol].status == "OPEN":
            self.logger.warning(f"Position already open for {symbol}")
            return None
        
        position = Position(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_time=datetime.now().timestamp()
        )
        
        self.positions[symbol] = position
        self.logger.info(f"Position OPENED: {direction} {quantity}x {symbol} @ {entry_price} | SL: {stop_loss} | TP: {take_profit}")
        
        return position
    
    async def close_position(self, symbol: str, exit_price: float, reason: str = "MANUAL"):
        """Close a position."""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        if position.status != "OPEN":
            return
        
        # Calculate P&L
        if position.direction == "BUY":
            pnl = (exit_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - exit_price) * position.quantity
        
        position.pnl = round(pnl, 2)
        position.status = reason
        
        # Move to closed list
        self.closed_positions.append(position)
        del self.positions[symbol]
        
        self.logger.info(f"Position CLOSED ({reason}): {symbol} @ {exit_price} | P&L: ₹{pnl:.2f}")
        
        # Publish exit order
        exit_order = {
            "symbol": symbol,
            "action": "SELL" if position.direction == "BUY" else "BUY",
            "quantity": position.quantity,
            "price": 0.0,  # Market order
            "type": "MARKET",
            "reason": reason
        }
        await bus.publish(EventType.ORDER_VALIDATION, exit_order)
    
    async def on_order_filled(self, execution: dict):
        """Handle order execution to track new positions."""
        # This is called when ExecutionAgent confirms a fill
        # We need entry_price, sl, tp from the original signal/order
        # For now, positions are opened via RiskAgent calling open_position
        pass
    
    async def on_tick(self, tick: dict):
        """Monitor prices for SL/TP hits."""
        symbol = tick.get('symbol')
        ltp = tick.get('ltp')
        
        if not symbol or not ltp:
            return
        
        position = self.positions.get(symbol)
        if not position or position.status != "OPEN":
            return
        
        # Update highest/lowest for trailing
        position.highest_price = max(position.highest_price, ltp)
        position.lowest_price = min(position.lowest_price, ltp)
        
        # Check Stop-Loss
        if position.direction == "BUY" and ltp <= position.current_stop:
            await self.close_position(symbol, ltp, "SL_HIT")
            return
        elif position.direction == "SELL" and ltp >= position.current_stop:
            await self.close_position(symbol, ltp, "SL_HIT")
            return
        
        # Check Take-Profit
        if position.direction == "BUY" and ltp >= position.take_profit:
            await self.close_position(symbol, ltp, "TP_HIT")
            return
        elif position.direction == "SELL" and ltp <= position.take_profit:
            await self.close_position(symbol, ltp, "TP_HIT")
            return
        
        # Update Trailing Stop
        if self.trailing_enabled:
            await self._update_trailing_stop(position, ltp)
    
    async def on_candle(self, candle: dict):
        """Store candles for ATR calculation."""
        symbol = candle.get('symbol')
        if not symbol:
            return
        
        if symbol not in self.recent_candles:
            self.recent_candles[symbol] = []
        
        self.recent_candles[symbol].append(candle)
        # Keep last 20 candles
        self.recent_candles[symbol] = self.recent_candles[symbol][-20:]
    
    async def _update_trailing_stop(self, position: Position, current_price: float):
        """Update trailing stop if price has moved favorably."""
        candles = self.recent_candles.get(position.symbol, [])
        if len(candles) < 5:
            return
        
        atr = calculate_atr(candles)
        
        new_stop = calculate_trailing_stop(
            current_price=current_price,
            entry_price=position.entry_price,
            current_stop=position.current_stop,
            atr=atr,
            direction=position.direction,
            trail_multiplier=1.0
        )
        
        if new_stop != position.current_stop:
            old_stop = position.current_stop
            position.current_stop = new_stop
            self.logger.info(f"Trailing Stop Updated: {position.symbol} | {old_stop} -> {new_stop}")
    
    async def _eod_monitor(self):
        """Monitor for end-of-day auto-close."""
        while self.is_running:
            now = datetime.now().time()
            
            if now >= self.eod_close_time:
                # Close all open positions
                for symbol in list(self.positions.keys()):
                    position = self.positions[symbol]
                    if position.status == "OPEN":
                        # Get last known price or use entry as fallback
                        exit_price = position.highest_price if position.direction == "BUY" else position.lowest_price
                        await self.close_position(symbol, exit_price, "EOD_EXIT")
                
                # Wait until next day
                await asyncio.sleep(3600 * 18)  # Sleep 18 hours
            else:
                await asyncio.sleep(60)  # Check every minute
    
    def get_stats(self) -> dict:
        """Get position statistics."""
        open_positions = self.get_all_open_positions()
        total_pnl = sum(p.pnl for p in self.closed_positions)
        
        return {
            "open_count": len(open_positions),
            "closed_count": len(self.closed_positions),
            "total_pnl": round(total_pnl, 2),
            "open_positions": [asdict(p) for p in open_positions],
            "recent_closed": [asdict(p) for p in self.closed_positions[-10:]]
        }

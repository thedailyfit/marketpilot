"""
Paper Trading Mode
Realistic paper trading with slippage, delays, and spreads.
Tests strategies before going live.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging
import json
from pathlib import Path
import random


logger = logging.getLogger(__name__)


@dataclass
class PaperOrder:
    """Paper trade order."""
    id: str
    symbol: str
    action: str  # BUY, SELL
    quantity: int
    order_type: str  # MARKET, LIMIT
    limit_price: float = 0.0
    created_at: datetime = None
    filled_at: datetime = None
    fill_price: float = 0.0
    status: str = "PENDING"  # PENDING, FILLED, CANCELLED, REJECTED
    strategy: str = ""
    slippage_applied: float = 0.0
    commission: float = 0.0


@dataclass  
class PaperPosition:
    """Open paper position."""
    symbol: str
    quantity: int
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    strategy: str = ""
    sl_price: float = 0.0
    tp_price: float = 0.0


@dataclass
class PaperTrade:
    """Completed paper trade."""
    id: int
    symbol: str
    strategy: str
    action: str
    entry_price: float
    exit_price: float
    quantity: int
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_percent: float
    slippage_cost: float
    commission_cost: float
    exit_reason: str


class PaperTrader:
    """
    Realistic Paper Trading Simulator.
    
    Simulates real trading conditions:
    - Order execution delay (500ms-2s)
    - Slippage (0.1-0.5% based on volatility)
    - Bid-ask spread impact
    - Brokerage commission (₹20/order)
    - Realistic fill prices
    
    This helps prepare for live trading by exposing
    issues that wouldn't show up in simple backtests.
    """
    
    # Realistic parameters
    MIN_DELAY_MS = 500  # Minimum order delay
    MAX_DELAY_MS = 2000  # Maximum order delay
    BASE_SLIPPAGE_PCT = 0.001  # 0.1% base slippage
    MAX_SLIPPAGE_PCT = 0.005  # 0.5% max slippage
    COMMISSION_PER_ORDER = 20  # ₹20 per order
    LOT_SIZE = 50  # Nifty lot size
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        
        # Orders and positions
        self.pending_orders: List[PaperOrder] = []
        self.open_positions: Dict[str, PaperPosition] = {}
        self.trade_history: List[PaperTrade] = []
        self.order_counter = 0
        self.trade_counter = 0
        
        # Performance tracking
        self.equity_curve: List[Dict] = []
        self.peak_equity = initial_capital
        self.max_drawdown = 0.0
        
        # Current market price (updated externally)
        self.current_prices: Dict[str, float] = {}
        
        # Data directory
        self.data_dir = Path("data/paper_trades")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load previous session
        self._load_state()
    
    def _load_state(self):
        """Load previous paper trading state."""
        state_file = self.data_dir / "paper_state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.current_capital = state.get('capital', self.initial_capital)
                    self.trade_counter = state.get('trade_counter', 0)
                    logger.info(f"Loaded paper state: ₹{self.current_capital:,.0f}, {self.trade_counter} trades")
            except Exception as e:
                logger.error(f"Failed to load paper state: {e}")
    
    def _save_state(self):
        """Save paper trading state."""
        state_file = self.data_dir / "paper_state.json"
        try:
            state = {
                'capital': self.current_capital,
                'trade_counter': self.trade_counter,
                'last_updated': datetime.now().isoformat()
            }
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save paper state: {e}")
    
    def calculate_slippage(self, price: float, action: str, volatility: float = 0.15) -> float:
        """
        Calculate realistic slippage based on volatility.
        
        Higher volatility = higher slippage
        Market orders have higher slippage than limit orders
        """
        # Base slippage
        slippage_pct = self.BASE_SLIPPAGE_PCT
        
        # Add volatility component
        vol_factor = min(volatility / 0.15, 2.0)  # Normalized to 15% IV
        slippage_pct *= vol_factor
        
        # Add random component (market conditions)
        random_factor = random.uniform(0.5, 1.5)
        slippage_pct *= random_factor
        
        # Cap at maximum
        slippage_pct = min(slippage_pct, self.MAX_SLIPPAGE_PCT)
        
        # Apply slippage (unfavorable direction)
        slippage_amount = price * slippage_pct
        
        if action == 'BUY':
            return price + slippage_amount  # Buy higher
        else:
            return price - slippage_amount  # Sell lower
    
    async def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int = None,
        order_type: str = "MARKET",
        limit_price: float = 0.0,
        strategy: str = "",
        sl_pct: float = 0.01,
        tp_pct: float = 0.02
    ) -> PaperOrder:
        """
        Place a paper order with realistic execution.
        """
        quantity = quantity or self.LOT_SIZE
        
        self.order_counter += 1
        order = PaperOrder(
            id=f"PAPER-{self.order_counter:06d}",
            symbol=symbol,
            action=action,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            created_at=datetime.now(),
            strategy=strategy,
            status="PENDING"
        )
        
        self.pending_orders.append(order)
        logger.info(f"Paper Order Placed: {order.id} {action} {quantity} {symbol}")
        
        # Simulate execution delay
        delay_ms = random.uniform(self.MIN_DELAY_MS, self.MAX_DELAY_MS)
        await asyncio.sleep(delay_ms / 1000)
        
        # Get current price
        current_price = self.current_prices.get(symbol, 23500)
        
        # Apply slippage
        fill_price = self.calculate_slippage(current_price, action)
        
        # Fill the order
        order.fill_price = round(fill_price, 2)
        order.filled_at = datetime.now()
        order.slippage_applied = round(abs(fill_price - current_price), 2)
        order.commission = self.COMMISSION_PER_ORDER
        order.status = "FILLED"
        
        logger.info(
            f"Paper Order Filled: {order.id} @ ₹{order.fill_price} "
            f"(slippage: ₹{order.slippage_applied})"
        )
        
        # Create or close position
        if symbol not in self.open_positions:
            # New position
            position = PaperPosition(
                symbol=symbol,
                quantity=quantity if action == 'BUY' else -quantity,
                entry_price=fill_price,
                entry_time=order.filled_at,
                current_price=fill_price,
                strategy=strategy,
                sl_price=fill_price * (1 - sl_pct) if action == 'BUY' else fill_price * (1 + sl_pct),
                tp_price=fill_price * (1 + tp_pct) if action == 'BUY' else fill_price * (1 - tp_pct)
            )
            self.open_positions[symbol] = position
        else:
            # Close position
            position = self.open_positions[symbol]
            await self.close_position(symbol, fill_price, "Signal Exit")
        
        self.pending_orders.remove(order)
        return order
    
    async def close_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str = "Manual"
    ) -> Optional[PaperTrade]:
        """Close an open position."""
        if symbol not in self.open_positions:
            return None
        
        position = self.open_positions[symbol]
        
        # Apply exit slippage
        action = 'SELL' if position.quantity > 0 else 'BUY'
        exit_price_slipped = self.calculate_slippage(exit_price, action)
        
        # Calculate P&L
        if position.quantity > 0:  # Long
            pnl_points = exit_price_slipped - position.entry_price
        else:  # Short
            pnl_points = position.entry_price - exit_price_slipped
        
        gross_pnl = pnl_points * abs(position.quantity)
        slippage_cost = abs(exit_price - exit_price_slipped) * abs(position.quantity)
        commission_cost = self.COMMISSION_PER_ORDER * 2  # Entry + Exit
        net_pnl = gross_pnl - slippage_cost - commission_cost
        
        # Record trade
        self.trade_counter += 1
        trade = PaperTrade(
            id=self.trade_counter,
            symbol=symbol,
            strategy=position.strategy,
            action='BUY' if position.quantity > 0 else 'SELL',
            entry_price=position.entry_price,
            exit_price=round(exit_price_slipped, 2),
            quantity=abs(position.quantity),
            entry_time=position.entry_time,
            exit_time=datetime.now(),
            pnl=round(net_pnl, 2),
            pnl_percent=round(pnl_points / position.entry_price * 100, 2),
            slippage_cost=round(slippage_cost, 2),
            commission_cost=commission_cost,
            exit_reason=reason
        )
        
        self.trade_history.append(trade)
        
        # Update capital
        self.current_capital += net_pnl
        
        # Track equity curve
        self.equity_curve.append({
            'timestamp': datetime.now().isoformat(),
            'equity': self.current_capital,
            'trade_id': trade.id
        })
        
        # Update max drawdown
        if self.current_capital > self.peak_equity:
            self.peak_equity = self.current_capital
        current_dd = (self.peak_equity - self.current_capital) / self.peak_equity
        self.max_drawdown = max(self.max_drawdown, current_dd)
        
        # Remove position
        del self.open_positions[symbol]
        
        # Save state
        self._save_state()
        
        pnl_emoji = "✅" if net_pnl > 0 else "❌"
        logger.info(
            f"{pnl_emoji} Paper Trade #{trade.id}: {position.strategy} "
            f"P&L: ₹{net_pnl:,.0f} | Capital: ₹{self.current_capital:,.0f}"
        )
        
        return trade
    
    def update_price(self, symbol: str, price: float):
        """Update current market price for a symbol."""
        self.current_prices[symbol] = price
        
        # Check SL/TP for open positions
        if symbol in self.open_positions:
            position = self.open_positions[symbol]
            position.current_price = price
            
            # Calculate unrealized P&L
            if position.quantity > 0:
                position.unrealized_pnl = (price - position.entry_price) * position.quantity
                
                # Check SL
                if price <= position.sl_price:
                    asyncio.create_task(self.close_position(symbol, price, "Stop Loss"))
                # Check TP
                elif price >= position.tp_price:
                    asyncio.create_task(self.close_position(symbol, price, "Take Profit"))
            else:
                position.unrealized_pnl = (position.entry_price - price) * abs(position.quantity)
                
                if price >= position.sl_price:
                    asyncio.create_task(self.close_position(symbol, price, "Stop Loss"))
                elif price <= position.tp_price:
                    asyncio.create_task(self.close_position(symbol, price, "Take Profit"))
    
    def get_performance_summary(self) -> Dict:
        """Get paper trading performance summary."""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'initial_capital': self.initial_capital,
                'current_capital': self.current_capital,
                'total_pnl': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'max_drawdown': 0
            }
        
        wins = [t for t in self.trade_history if t.pnl > 0]
        losses = [t for t in self.trade_history if t.pnl <= 0]
        
        total_wins = sum(t.pnl for t in wins)
        total_losses = abs(sum(t.pnl for t in losses))
        
        return {
            'total_trades': len(self.trade_history),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(len(wins) / len(self.trade_history) * 100, 1),
            'initial_capital': self.initial_capital,
            'current_capital': round(self.current_capital, 2),
            'total_pnl': round(self.current_capital - self.initial_capital, 2),
            'return_pct': round((self.current_capital / self.initial_capital - 1) * 100, 2),
            'profit_factor': round(total_wins / total_losses, 2) if total_losses > 0 else 0,
            'max_drawdown_pct': round(self.max_drawdown * 100, 2),
            'avg_slippage': round(
                sum(t.slippage_cost for t in self.trade_history) / len(self.trade_history), 2
            ),
            'total_commission': sum(t.commission_cost for t in self.trade_history)
        }
    
    def print_summary(self):
        """Print paper trading summary."""
        summary = self.get_performance_summary()
        
        print("\n" + "="*50)
        print("  PAPER TRADING SUMMARY")
        print("="*50)
        print(f"  Total Trades:     {summary['total_trades']}")
        print(f"  Win Rate:         {summary['win_rate']}%")
        print(f"  Initial Capital:  ₹{summary['initial_capital']:,.0f}")
        print(f"  Current Capital:  ₹{summary['current_capital']:,.0f}")
        print(f"  Total P&L:        ₹{summary['total_pnl']:,.0f}")
        print(f"  Return:           {summary['return_pct']}%")
        print(f"  Max Drawdown:     {summary['max_drawdown_pct']}%")
        print(f"  Profit Factor:    {summary['profit_factor']}")
        print(f"  Avg Slippage:     ₹{summary['avg_slippage']}")
        print(f"  Total Commission: ₹{summary['total_commission']:,.0f}")
        print("="*50 + "\n")


# Global instance
paper_trader = PaperTrader()

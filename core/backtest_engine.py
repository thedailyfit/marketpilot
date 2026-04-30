"""
Backtesting Engine
Tests trading strategies on historical data before going live.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
import logging
import json
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Single trade record."""
    id: int
    entry_time: datetime
    exit_time: Optional[datetime]
    symbol: str
    strategy: str
    direction: str  # BUY or SELL
    entry_price: float
    exit_price: float = 0.0
    quantity: int = 50
    sl_price: float = 0.0
    tp_price: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    status: str = "OPEN"  # OPEN, WIN, LOSS, EVEN
    reason: str = ""


@dataclass
class BacktestResult:
    """Complete backtest results."""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    max_drawdown_percent: float
    sharpe_ratio: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    max_win: float
    max_loss: float
    avg_trade_duration: float  # in minutes
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)


class BacktestEngine:
    """
    Backtesting engine for validating trading strategies.
    Tests on historical data with realistic slippage and commissions.
    """
    
    SLIPPAGE_PCT = 0.001  # 0.1% slippage (more realistic)
    COMMISSION_PER_ORDER = 20  # ₹20 per order (Upstox)
    LOT_SIZE = 25  # Reduced lot size for risk management
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.trades: List[Trade] = []
        self.trade_counter = 0
        self.equity_curve: List[float] = []
        self.peak_equity = initial_capital
        self.drawdown_curve: List[float] = []
        
        # Data storage
        self.data: pd.DataFrame = None
        self.current_idx = 0
        
    def load_data(self, data: pd.DataFrame):
        """
        Load OHLCV data for backtesting.
        
        Expected columns: datetime, open, high, low, close, volume
        """
        required_cols = ['datetime', 'open', 'high', 'low', 'close']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")
        
        self.data = data.sort_values('datetime').reset_index(drop=True)
        logger.info(f"Loaded {len(self.data)} candles for backtesting")
    
    def generate_sample_data(self, days: int = 60, interval_mins: int = 5):
        """
        Generate realistic sample OHLCV data for testing.
        Uses random walk with mean reversion (like real markets).
        """
        np.random.seed(42)  # Reproducible results
        
        # Generate timestamps (Indian market hours: 9:15 AM - 3:30 PM)
        start_date = datetime.now() - timedelta(days=days)
        timestamps = []
        
        for day in range(days):
            date = start_date + timedelta(days=day)
            if date.weekday() >= 5:  # Skip weekends
                continue
            
            # Market hours
            market_open = date.replace(hour=9, minute=15, second=0)
            market_close = date.replace(hour=15, minute=30, second=0)
            
            current = market_open
            while current < market_close:
                timestamps.append(current)
                current += timedelta(minutes=interval_mins)
        
        n = len(timestamps)
        
        # Price generation with REALISTIC volatility
        # Indian markets typically move 0.5-1.5% per day
        base_price = 23500
        prices = [base_price]
        volatility = 0.004  # 0.4% per candle (more realistic)
        
        for i in range(1, n):
            # Mean reversion factor
            mean_revert = (base_price - prices[-1]) * 0.001
            # Random change
            change = np.random.normal(mean_revert, prices[-1] * volatility)
            new_price = prices[-1] + change
            prices.append(new_price)
        
        # Generate OHLC from close prices
        data = []
        for i, ts in enumerate(timestamps):
            close = prices[i]
            volatility_factor = np.random.uniform(0.0005, 0.002)
            
            # Generate realistic OHLC
            high_var = close * volatility_factor * np.random.uniform(0.3, 1.5)
            low_var = close * volatility_factor * np.random.uniform(0.3, 1.5)
            open_var = close * volatility_factor * np.random.uniform(-0.5, 0.5)
            
            open_price = close + open_var
            high = max(open_price, close) + high_var
            low = min(open_price, close) - low_var
            
            # Volume with intraday pattern (high at open/close)
            hour = ts.hour + ts.minute / 60
            if hour < 10 or hour > 15:
                vol_multiplier = 2.0
            elif hour > 12 and hour < 13.5:
                vol_multiplier = 0.6  # Lunch slump
            else:
                vol_multiplier = 1.0
            
            volume = int(50000 * vol_multiplier * np.random.uniform(0.5, 2.0))
            
            data.append({
                'datetime': ts,
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': volume
            })
        
        self.data = pd.DataFrame(data)
        logger.info(f"Generated {len(self.data)} sample candles")
        return self.data
    
    def run_backtest(
        self,
        strategy_func: Callable,
        strategy_name: str,
        params: Dict = None
    ) -> BacktestResult:
        """
        Run backtest with given strategy function.
        
        Args:
            strategy_func: Function(data_slice, params) -> signal dict
            strategy_name: Name for reporting
            params: Strategy parameters
        
        Returns:
            BacktestResult with all metrics
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        # Reset state
        self.current_capital = self.initial_capital
        self.trades = []
        self.trade_counter = 0
        self.equity_curve = [self.initial_capital]
        self.peak_equity = self.initial_capital
        self.drawdown_curve = [0]
        
        params = params or {}
        open_trade: Optional[Trade] = None
        
        # Iterate through data
        lookback = params.get('lookback', 20)
        
        for i in range(lookback, len(self.data)):
            current_candle = self.data.iloc[i]
            data_slice = self.data.iloc[i-lookback:i+1]
            
            current_time = current_candle['datetime']
            current_price = current_candle['close']
            high = current_candle['high']
            low = current_candle['low']
            
            # Check if open trade hit SL/TP
            if open_trade:
                # Check stop loss
                if open_trade.direction == "BUY":
                    if low <= open_trade.sl_price:
                        self._close_trade(open_trade, open_trade.sl_price, current_time, "SL Hit")
                        open_trade = None
                    elif high >= open_trade.tp_price:
                        self._close_trade(open_trade, open_trade.tp_price, current_time, "TP Hit")
                        open_trade = None
                else:  # SELL
                    if high >= open_trade.sl_price:
                        self._close_trade(open_trade, open_trade.sl_price, current_time, "SL Hit")
                        open_trade = None
                    elif low <= open_trade.tp_price:
                        self._close_trade(open_trade, open_trade.tp_price, current_time, "TP Hit")
                        open_trade = None
            
            # Get signal from strategy (only if no open trade)
            if not open_trade:
                signal = strategy_func(data_slice, params)
                
                if signal and signal.get('action') in ['BUY', 'SELL']:
                    # Apply slippage
                    entry_price = current_price
                    if signal['action'] == 'BUY':
                        entry_price *= (1 + self.SLIPPAGE_PCT)
                    else:
                        entry_price *= (1 - self.SLIPPAGE_PCT)
                    
                    # Calculate SL/TP
                    sl_pct = signal.get('sl_pct', 0.01)  # Default 1%
                    tp_pct = signal.get('tp_pct', 0.02)  # Default 2%
                    
                    if signal['action'] == 'BUY':
                        sl_price = entry_price * (1 - sl_pct)
                        tp_price = entry_price * (1 + tp_pct)
                    else:
                        sl_price = entry_price * (1 + sl_pct)
                        tp_price = entry_price * (1 - tp_pct)
                    
                    # Create trade
                    self.trade_counter += 1
                    open_trade = Trade(
                        id=self.trade_counter,
                        entry_time=current_time,
                        exit_time=None,
                        symbol=params.get('symbol', 'NIFTY'),
                        strategy=strategy_name,
                        direction=signal['action'],
                        entry_price=round(entry_price, 2),
                        quantity=self.LOT_SIZE,
                        sl_price=round(sl_price, 2),
                        tp_price=round(tp_price, 2)
                    )
            
            # Update equity curve
            self.equity_curve.append(self.current_capital)
            
            # Update drawdown
            if self.current_capital > self.peak_equity:
                self.peak_equity = self.current_capital
            drawdown = (self.peak_equity - self.current_capital) / self.peak_equity
            self.drawdown_curve.append(drawdown)
        
        # Close any remaining open trade at last price
        if open_trade:
            last_price = self.data.iloc[-1]['close']
            self._close_trade(open_trade, last_price, self.data.iloc[-1]['datetime'], "End of Data")
        
        # Calculate final metrics
        return self._calculate_results(strategy_name)
    
    def _close_trade(self, trade: Trade, exit_price: float, exit_time: datetime, reason: str):
        """Close a trade and update capital."""
        # Apply slippage on exit
        if trade.direction == "BUY":
            exit_price *= (1 - self.SLIPPAGE_PCT)
        else:
            exit_price *= (1 + self.SLIPPAGE_PCT)
        
        trade.exit_price = round(exit_price, 2)
        trade.exit_time = exit_time
        trade.reason = reason
        
        # Calculate P&L
        if trade.direction == "BUY":
            points = trade.exit_price - trade.entry_price
        else:
            points = trade.entry_price - trade.exit_price
        
        trade.pnl = points * trade.quantity - (2 * self.COMMISSION_PER_ORDER)
        trade.pnl_percent = points / trade.entry_price
        
        # Update status
        if trade.pnl > 0:
            trade.status = "WIN"
        elif trade.pnl < 0:
            trade.status = "LOSS"
        else:
            trade.status = "EVEN"
        
        # Update capital
        self.current_capital += trade.pnl
        self.trades.append(trade)
    
    def _calculate_results(self, strategy_name: str) -> BacktestResult:
        """Calculate all backtest metrics."""
        if not self.trades:
            return BacktestResult(
                strategy_name=strategy_name,
                start_date=self.data.iloc[0]['datetime'],
                end_date=self.data.iloc[-1]['datetime'],
                initial_capital=self.initial_capital,
                final_capital=self.current_capital,
                total_trades=0,
                wins=0, losses=0, win_rate=0,
                total_pnl=0, max_drawdown=0, max_drawdown_percent=0,
                sharpe_ratio=0, profit_factor=0,
                avg_win=0, avg_loss=0, max_win=0, max_loss=0,
                avg_trade_duration=0
            )
        
        wins = [t for t in self.trades if t.status == "WIN"]
        losses = [t for t in self.trades if t.status == "LOSS"]
        
        win_pnls = [t.pnl for t in wins] if wins else [0]
        loss_pnls = [abs(t.pnl) for t in losses] if losses else [0]
        
        total_wins = sum(win_pnls)
        total_losses = sum(loss_pnls)
        
        # Sharpe Ratio (annualized)
        returns = []
        for i in range(1, len(self.equity_curve)):
            ret = (self.equity_curve[i] - self.equity_curve[i-1]) / self.equity_curve[i-1]
            returns.append(ret)
        
        if returns and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 75)  # 75 candles per day
        else:
            sharpe = 0
        
        # Average trade duration
        durations = []
        for t in self.trades:
            if t.exit_time:
                dur = (t.exit_time - t.entry_time).total_seconds() / 60
                durations.append(dur)
        
        return BacktestResult(
            strategy_name=strategy_name,
            start_date=self.data.iloc[0]['datetime'],
            end_date=self.data.iloc[-1]['datetime'],
            initial_capital=self.initial_capital,
            final_capital=round(self.current_capital, 2),
            total_trades=len(self.trades),
            wins=len(wins),
            losses=len(losses),
            win_rate=round(len(wins) / len(self.trades) * 100, 2) if self.trades else 0,
            total_pnl=round(self.current_capital - self.initial_capital, 2),
            max_drawdown=round(max(self.drawdown_curve) * self.initial_capital, 2),
            max_drawdown_percent=round(max(self.drawdown_curve) * 100, 2),
            sharpe_ratio=round(sharpe, 2),
            profit_factor=round(total_wins / total_losses, 2) if total_losses > 0 else 0,
            avg_win=round(np.mean(win_pnls), 2) if wins else 0,
            avg_loss=round(np.mean(loss_pnls), 2) if losses else 0,
            max_win=round(max(win_pnls), 2) if wins else 0,
            max_loss=round(max(loss_pnls), 2) if losses else 0,
            avg_trade_duration=round(np.mean(durations), 1) if durations else 0,
            trades=self.trades,
            equity_curve=self.equity_curve,
            drawdown_curve=self.drawdown_curve
        )
    
    def print_report(self, result: BacktestResult):
        """Print formatted backtest report."""
        print("\n" + "="*60)
        print(f"  BACKTEST REPORT: {result.strategy_name}")
        print("="*60)
        print(f"  Period: {result.start_date.date()} to {result.end_date.date()}")
        print(f"  Initial Capital: ₹{result.initial_capital:,.0f}")
        print(f"  Final Capital:   ₹{result.final_capital:,.0f}")
        print("-"*60)
        print(f"  Total P&L:       ₹{result.total_pnl:,.0f}")
        print(f"  Return:          {result.total_pnl/result.initial_capital*100:.1f}%")
        print("-"*60)
        print(f"  Total Trades:    {result.total_trades}")
        print(f"  Wins:            {result.wins} ({result.win_rate}%)")
        print(f"  Losses:          {result.losses}")
        print("-"*60)
        print(f"  Avg Win:         ₹{result.avg_win:,.0f}")
        print(f"  Avg Loss:        ₹{result.avg_loss:,.0f}")
        print(f"  Max Win:         ₹{result.max_win:,.0f}")
        print(f"  Max Loss:        ₹{result.max_loss:,.0f}")
        print("-"*60)
        print(f"  Sharpe Ratio:    {result.sharpe_ratio}")
        print(f"  Profit Factor:   {result.profit_factor}")
        print(f"  Max Drawdown:    ₹{result.max_drawdown:,.0f} ({result.max_drawdown_percent}%)")
        print("-"*60)
        print(f"  Avg Trade Duration: {result.avg_trade_duration} mins")
        print("="*60 + "\n")
    
    def save_results(self, result: BacktestResult, filepath: str):
        """Save backtest results to JSON."""
        data = {
            'strategy_name': result.strategy_name,
            'start_date': str(result.start_date),
            'end_date': str(result.end_date),
            'initial_capital': result.initial_capital,
            'final_capital': result.final_capital,
            'total_trades': result.total_trades,
            'wins': result.wins,
            'losses': result.losses,
            'win_rate': result.win_rate,
            'total_pnl': result.total_pnl,
            'max_drawdown': result.max_drawdown,
            'max_drawdown_percent': result.max_drawdown_percent,
            'sharpe_ratio': result.sharpe_ratio,
            'profit_factor': result.profit_factor,
            'avg_win': result.avg_win,
            'avg_loss': result.avg_loss,
            'equity_curve': result.equity_curve[-100:]  # Last 100 points
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Results saved to {filepath}")


# Global instance
backtest_engine = BacktestEngine()

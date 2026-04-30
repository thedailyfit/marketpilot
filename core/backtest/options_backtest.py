"""
Options Backtest Engine
Full options backtesting with realistic fills, theta decay, and IV tracking.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Callable, Tuple
from pathlib import Path
import json

from core.options import OptionSnapshot
from .options_replay import OptionsReplayEngine, options_replay_engine
from .fill_simulator import FillSimulator, FillResult, Aggression, fill_simulator


@dataclass
class OptionsTrade:
    """Single options trade with full Greeks tracking."""
    id: int
    entry_time: int          # Unix timestamp
    exit_time: Optional[int]
    
    # Option details
    symbol: str
    strike: float
    expiry: str
    option_type: str         # CE or PE
    
    # Position
    direction: str           # BUY or SELL
    quantity: int
    
    # Entry state
    entry_price: float
    entry_iv: float
    entry_delta: float
    entry_theta: float
    entry_vega: float
    
    # Exit state
    exit_price: float = 0.0
    exit_iv: float = 0.0
    exit_delta: float = 0.0
    
    # P&L decomposition
    gross_pnl: float = 0.0
    delta_pnl: float = 0.0      # From direction
    theta_cost: float = 0.0     # From time decay
    iv_impact: float = 0.0      # From IV change
    spread_cost: float = 0.0    # From bid-ask
    slippage_cost: float = 0.0  # From slippage
    net_pnl: float = 0.0
    
    # Status
    status: str = "OPEN"        # OPEN, WIN, LOSS, EVEN
    exit_reason: str = ""


@dataclass
class OptionsBacktestResult:
    """Complete options backtest results."""
    strategy_name: str
    symbol: str
    start_date: date
    end_date: date
    
    # Summary
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    
    # P&L
    total_pnl: float
    total_delta_pnl: float
    theta_decay_cost: float      # Total theta paid
    spread_slippage_cost: float  # Total spread + slippage
    iv_change_impact: float      # Total IV P&L
    
    # Risk metrics
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    
    # Execution stats
    avg_spread_cost: float
    avg_slippage: float
    fill_rate: float
    
    # Regime breakdown
    regime_breakdown: Dict[str, float] = field(default_factory=dict)
    
    # Trade list
    trades: List[OptionsTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "dates": f"{self.start_date} to {self.end_date}",
            "total_trades": self.total_trades,
            "win_rate": f"{self.win_rate:.1f}%",
            "total_pnl": round(self.total_pnl, 2),
            "delta_pnl": round(self.total_delta_pnl, 2),
            "theta_cost": round(self.theta_decay_cost, 2),
            "spread_slippage_cost": round(self.spread_slippage_cost, 2),
            "iv_impact": round(self.iv_change_impact, 2),
            "max_drawdown_pct": f"{self.max_drawdown_pct:.1f}%",
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "fill_rate": f"{self.fill_rate:.1f}%",
            "regime_breakdown": self.regime_breakdown
        }


@dataclass
class WalkForwardResult:
    """Walk-forward validation result."""
    train_result: OptionsBacktestResult
    test_result: OptionsBacktestResult
    degradation_pct: float     # How much worse is test vs train
    is_robust: bool            # True if test holds up


class OptionsBacktestEngine:
    """
    Options-specific backtest engine.
    
    Features:
    - Uses OptionsReplayEngine for data
    - Uses FillSimulator for realistic fills
    - Tracks theta decay minute-by-minute
    - Tracks IV evolution impact
    - Walk-forward validation
    - Regime-segmented results
    """
    
    LOT_SIZE = 25  # NIFTY/BANKNIFTY lot size
    
    def __init__(self, initial_capital: float = 100000):
        self.logger = logging.getLogger("OptionsBacktestEngine")
        self.initial_capital = initial_capital
        self.replay_engine = OptionsReplayEngine()
        self.fill_sim = FillSimulator()
        
        # State
        self.capital = initial_capital
        self.trades: List[OptionsTrade] = []
        self.trade_counter = 0
        self.equity_curve: List[float] = []
        
    def run_backtest(
        self,
        strategy_func: Callable,
        symbol: str,
        dates: List[date],
        params: Dict = None,
        aggression: Aggression = Aggression.NORMAL
    ) -> OptionsBacktestResult:
        """
        Run full options backtest.
        
        Args:
            strategy_func: Function(chain, spot, params) -> signal dict
                Signal: {action: BUY/SELL, strike, expiry, option_type, sl_pct, tp_pct}
            symbol: NIFTY or BANKNIFTY
            dates: List of dates to backtest
            params: Strategy parameters
            aggression: Order aggression level
        
        Returns:
            OptionsBacktestResult with full metrics
        """
        params = params or {}
        self._reset()
        
        self.logger.info(f"🔬 Starting Options Backtest: {symbol} over {len(dates)} days")
        
        open_position: Optional[OptionsTrade] = None
        
        for target_date in dates:
            # Load session data
            snapshot_count = self.replay_engine.load_session(symbol, target_date)
            
            if snapshot_count == 0:
                self.logger.warning(f"No data for {target_date}, skipping")
                continue
            
            # Iterate through snapshots
            for timestamp, chain in self.replay_engine.iterate_snapshots():
                spot_price = self.replay_engine.get_index_price_at(timestamp, chain)
                
                if spot_price == 0:
                    continue
                
                # Check open position
                if open_position:
                    # Update position Greeks
                    current_opt = self._find_option(
                        chain, 
                        open_position.strike, 
                        open_position.expiry, 
                        open_position.option_type
                    )
                    
                    if current_opt:
                        # Check SL/TP
                        exit_signal = self._check_exit(
                            open_position, current_opt, spot_price, params
                        )
                        
                        if exit_signal:
                            fill = self.fill_sim.simulate_fill(
                                current_opt,
                                "SELL" if open_position.direction == "BUY" else "BUY",
                                open_position.quantity,
                                aggression,
                                spot_price
                            )
                            
                            if fill.filled:
                                self._close_position(
                                    open_position, 
                                    current_opt, 
                                    fill, 
                                    timestamp,
                                    exit_signal
                                )
                                open_position = None
                
                # Generate new signal if no position
                if not open_position:
                    signal = strategy_func(chain, spot_price, params)
                    
                    if signal and signal.get('action') in ['BUY', 'SELL']:
                        # Find the option
                        target_opt = self._find_option(
                            chain,
                            signal['strike'],
                            signal['expiry'],
                            signal['option_type']
                        )
                        
                        if target_opt:
                            # Simulate fill
                            fill = self.fill_sim.simulate_fill(
                                target_opt,
                                signal['action'],
                                params.get('quantity', self.LOT_SIZE),
                                aggression,
                                spot_price
                            )
                            
                            if fill.filled:
                                open_position = self._open_position(
                                    target_opt,
                                    signal,
                                    fill,
                                    timestamp,
                                    params
                                )
                
                # Update equity curve
                self.equity_curve.append(self.capital)
        
        # Close any remaining position
        if open_position:
            # Get last known price
            last_chain = self.replay_engine.get_chain_at(
                self.replay_engine.timestamps[-1]
            )
            last_opt = self._find_option(
                last_chain,
                open_position.strike,
                open_position.expiry,
                open_position.option_type
            )
            
            if last_opt:
                fill = self.fill_sim.simulate_fill(
                    last_opt,
                    "SELL" if open_position.direction == "BUY" else "BUY",
                    open_position.quantity,
                    Aggression.AGGRESSIVE  # Force close
                )
                if fill.filled:
                    self._close_position(
                        open_position, last_opt, fill,
                        self.replay_engine.timestamps[-1],
                        "End of Data"
                    )
        
        # Calculate results
        return self._calculate_results(symbol, dates, params.get('strategy_name', 'Unknown'))
    
    def run_walk_forward(
        self,
        strategy_func: Callable,
        symbol: str,
        dates: List[date],
        params: Dict = None,
        train_ratio: float = 0.7
    ) -> WalkForwardResult:
        """
        Walk-forward validation.
        
        Args:
            strategy_func: Strategy function
            symbol: Symbol to test
            dates: All dates
            params: Strategy params
            train_ratio: Portion for training (default 70%)
        
        Returns:
            WalkForwardResult with train/test comparison
        """
        split_idx = int(len(dates) * train_ratio)
        train_dates = dates[:split_idx]
        test_dates = dates[split_idx:]
        
        self.logger.info(f"📊 Walk-Forward: {len(train_dates)} train, {len(test_dates)} test days")
        
        # Run on training period
        train_result = self.run_backtest(strategy_func, symbol, train_dates, params)
        
        # Run on test period
        test_result = self.run_backtest(strategy_func, symbol, test_dates, params)
        
        # Calculate degradation
        if train_result.win_rate > 0:
            degradation = (train_result.win_rate - test_result.win_rate) / train_result.win_rate * 100
        else:
            degradation = 0
        
        # Check if robust (test performance within 20% of train)
        is_robust = degradation < 20 and test_result.win_rate > 40
        
        return WalkForwardResult(
            train_result=train_result,
            test_result=test_result,
            degradation_pct=round(degradation, 1),
            is_robust=is_robust
        )
    
    def _reset(self):
        """Reset engine state."""
        self.capital = self.initial_capital
        self.trades = []
        self.trade_counter = 0
        self.equity_curve = [self.initial_capital]
        self.fill_sim.reset_stats()
    
    def _find_option(
        self, 
        chain: List[OptionSnapshot], 
        strike: float, 
        expiry: str, 
        option_type: str
    ) -> Optional[OptionSnapshot]:
        """Find option in chain."""
        for opt in chain:
            if (opt.strike == strike and 
                opt.expiry == expiry and 
                opt.option_type == option_type.upper()):
                return opt
        return None
    
    def _open_position(
        self,
        snapshot: OptionSnapshot,
        signal: dict,
        fill: FillResult,
        timestamp: int,
        params: dict
    ) -> OptionsTrade:
        """Open a new position."""
        self.trade_counter += 1
        
        trade = OptionsTrade(
            id=self.trade_counter,
            entry_time=timestamp,
            exit_time=None,
            symbol=snapshot.symbol,
            strike=snapshot.strike,
            expiry=snapshot.expiry,
            option_type=snapshot.option_type,
            direction=signal['action'],
            quantity=params.get('quantity', self.LOT_SIZE),
            entry_price=fill.fill_price,
            entry_iv=snapshot.iv,
            entry_delta=snapshot.delta,
            entry_theta=snapshot.theta,
            entry_vega=snapshot.vega,
            spread_cost=fill.spread_cost * params.get('quantity', self.LOT_SIZE),
            slippage_cost=fill.slippage * params.get('quantity', self.LOT_SIZE)
        )
        
        self.logger.debug(
            f"📈 Opened: {signal['action']} {snapshot.strike}{snapshot.option_type} "
            f"@ ₹{fill.fill_price:.2f} (IV={snapshot.iv:.2%})"
        )
        
        return trade
    
    def _check_exit(
        self,
        position: OptionsTrade,
        current: OptionSnapshot,
        spot_price: float,
        params: dict
    ) -> Optional[str]:
        """Check if position should exit."""
        sl_pct = params.get('sl_pct', 0.30)  # 30% SL default
        tp_pct = params.get('tp_pct', 0.50)  # 50% TP default
        
        current_price = current.ltp
        entry_price = position.entry_price
        
        if position.direction == "BUY":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        if pnl_pct <= -sl_pct:
            return "SL Hit"
        elif pnl_pct >= tp_pct:
            return "TP Hit"
        
        return None
    
    def _close_position(
        self,
        position: OptionsTrade,
        exit_snapshot: OptionSnapshot,
        fill: FillResult,
        timestamp: int,
        reason: str
    ):
        """Close position and calculate P&L components."""
        position.exit_time = timestamp
        position.exit_price = fill.fill_price
        position.exit_iv = exit_snapshot.iv
        position.exit_delta = exit_snapshot.delta
        position.exit_reason = reason
        
        # Calculate P&L components
        qty = position.quantity
        
        # Gross P&L
        if position.direction == "BUY":
            position.gross_pnl = (fill.fill_price - position.entry_price) * qty
        else:
            position.gross_pnl = (position.entry_price - fill.fill_price) * qty
        
        # Delta P&L (what direction gave us)
        position.delta_pnl = position.gross_pnl
        
        # Theta cost (estimated from time held)
        time_held_days = (timestamp - position.entry_time) / 86400
        position.theta_cost = abs(position.entry_theta) * time_held_days * qty
        
        # IV impact (vega × change in IV)
        iv_change = exit_snapshot.iv - position.entry_iv
        position.iv_impact = position.entry_vega * iv_change * 100 * qty
        
        # Add exit spread/slippage
        position.spread_cost += fill.spread_cost * qty
        position.slippage_cost += fill.slippage * qty
        
        # Net P&L
        position.net_pnl = (
            position.gross_pnl 
            - position.theta_cost 
            + position.iv_impact 
            - position.spread_cost 
            - position.slippage_cost
        )
        
        # Status
        if position.net_pnl > 0:
            position.status = "WIN"
        elif position.net_pnl < 0:
            position.status = "LOSS"
        else:
            position.status = "EVEN"
        
        # Update capital
        self.capital += position.net_pnl
        self.trades.append(position)
        
        self.logger.debug(
            f"📉 Closed: {position.strike}{position.option_type} "
            f"Net P&L=₹{position.net_pnl:.0f} ({reason})"
        )
    
    def _calculate_results(
        self, 
        symbol: str, 
        dates: List[date],
        strategy_name: str
    ) -> OptionsBacktestResult:
        """Calculate final backtest metrics."""
        wins = [t for t in self.trades if t.status == "WIN"]
        losses = [t for t in self.trades if t.status == "LOSS"]
        
        total_pnl = sum(t.net_pnl for t in self.trades)
        total_delta = sum(t.delta_pnl for t in self.trades)
        total_theta = sum(t.theta_cost for t in self.trades)
        total_iv = sum(t.iv_impact for t in self.trades)
        total_spread = sum(t.spread_cost + t.slippage_cost for t in self.trades)
        
        # Drawdown
        peak = self.initial_capital
        max_dd = 0
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
        
        # Fill stats
        fill_stats = self.fill_sim.get_stats()
        
        return OptionsBacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=dates[0] if dates else date.today(),
            end_date=dates[-1] if dates else date.today(),
            total_trades=len(self.trades),
            wins=len(wins),
            losses=len(losses),
            win_rate=len(wins) / len(self.trades) * 100 if self.trades else 0,
            total_pnl=round(total_pnl, 2),
            total_delta_pnl=round(total_delta, 2),
            theta_decay_cost=round(total_theta, 2),
            spread_slippage_cost=round(total_spread, 2),
            iv_change_impact=round(total_iv, 2),
            max_drawdown=round(max_dd * self.initial_capital, 2),
            max_drawdown_pct=round(max_dd * 100, 1),
            sharpe_ratio=0,  # TODO: Calculate properly
            profit_factor=abs(sum(t.net_pnl for t in wins)) / abs(sum(t.net_pnl for t in losses)) if losses else 0,
            avg_spread_cost=fill_stats['avg_spread_cost'],
            avg_slippage=fill_stats['avg_slippage'],
            fill_rate=fill_stats['fill_rate'],
            trades=self.trades,
            equity_curve=self.equity_curve
        )
    
    def print_report(self, result: OptionsBacktestResult):
        """Print formatted options backtest report."""
        print("\n" + "=" * 70)
        print(f"  OPTIONS BACKTEST REPORT: {result.strategy_name}")
        print("=" * 70)
        print(f"  Symbol: {result.symbol}")
        print(f"  Period: {result.start_date} to {result.end_date}")
        print("-" * 70)
        print(f"  Total Trades: {result.total_trades}")
        print(f"  Wins: {result.wins} | Losses: {result.losses}")
        print(f"  Win Rate: {result.win_rate:.1f}%")
        print("-" * 70)
        print("  P&L DECOMPOSITION:")
        print(f"    Net P&L:         ₹{result.total_pnl:,.0f}")
        print(f"    ├─ Delta P&L:    ₹{result.total_delta_pnl:,.0f}")
        print(f"    ├─ Theta Cost:   ₹{result.theta_decay_cost:,.0f}")
        print(f"    ├─ IV Impact:    ₹{result.iv_change_impact:,.0f}")
        print(f"    └─ Spread/Slip:  ₹{result.spread_slippage_cost:,.0f}")
        print("-" * 70)
        print("  EXECUTION QUALITY:")
        print(f"    Fill Rate: {result.fill_rate:.1f}%")
        print(f"    Avg Spread Cost: ₹{result.avg_spread_cost:.2f}")
        print(f"    Avg Slippage: ₹{result.avg_slippage:.2f}")
        print("-" * 70)
        print(f"  Max Drawdown: ₹{result.max_drawdown:,.0f} ({result.max_drawdown_pct:.1f}%)")
        print(f"  Profit Factor: {result.profit_factor:.2f}")
        print("=" * 70 + "\n")


# Singleton
options_backtest_engine = OptionsBacktestEngine()

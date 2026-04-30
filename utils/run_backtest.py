"""
Backtest Runner
Quick script to run backtests on all 3 profitable strategies.
"""
import sys
sys.path.insert(0, '.')

from core.backtest_engine import BacktestEngine
from agents.trading.strategies.theta_decay import theta_decay_strategy_func
from agents.trading.strategies.orb import orb_strategy_func
from agents.trading.strategies.oi_directional import oi_directional_strategy_func
from agents.strategy_selector import multi_strategy_selector_func


def run_all_backtests():
    """Run backtests for all 3 strategies and compare."""
    
    print("\n" + "="*70)
    print("  MARKETPILOT AI - MULTI-STRATEGY BACKTEST")
    print("="*70)
    
    # Initialize engine
    engine = BacktestEngine(initial_capital=100000)
    
    # Generate sample data (60 trading days)
    print("\n📊 Generating 60 days of sample market data...")
    engine.generate_sample_data(days=60, interval_mins=5)
    print(f"   Generated {len(engine.data)} candles")
    
    # Results storage
    results = []
    
    # ===== Strategy 1: Theta Decay =====
    print("\n🧪 Testing Strategy 1: THETA DECAY (Iron Condor)")
    print("-" * 50)
    
    result1 = engine.run_backtest(
        strategy_func=theta_decay_strategy_func,
        strategy_name="Theta Decay",
        params={'vix': 15, 'lookback': 20}
    )
    results.append(result1)
    engine.print_report(result1)
    
    # Reset for next test
    engine = BacktestEngine(initial_capital=100000)
    engine.generate_sample_data(days=60, interval_mins=5)
    
    # ===== Strategy 2: ORB =====
    print("\n🧪 Testing Strategy 2: OPENING RANGE BREAKOUT (ORB)")
    print("-" * 50)
    
    result2 = engine.run_backtest(
        strategy_func=orb_strategy_func,
        strategy_name="ORB Breakout",
        params={'lookback': 20}
    )
    results.append(result2)
    engine.print_report(result2)
    
    # Reset for next test
    engine = BacktestEngine(initial_capital=100000)
    engine.generate_sample_data(days=60, interval_mins=5)
    
    # ===== Strategy 3: OI Directional =====
    print("\n🧪 Testing Strategy 3: OI-BASED DIRECTIONAL")
    print("-" * 50)
    
    result3 = engine.run_backtest(
        strategy_func=oi_directional_strategy_func,
        strategy_name="OI Directional",
        params={'lookback': 20, 'pcr': 1.15}
    )
    results.append(result3)
    engine.print_report(result3)
    
    # Reset for next test
    engine = BacktestEngine(initial_capital=100000)
    engine.generate_sample_data(days=60, interval_mins=5)
    
    # ===== Multi-Strategy Selector =====
    print("\n🧪 Testing MULTI-STRATEGY SELECTOR (Auto-Select)")
    print("-" * 50)
    
    result4 = engine.run_backtest(
        strategy_func=multi_strategy_selector_func,
        strategy_name="Multi-Strategy Selector",
        params={'lookback': 20, 'vix': 15}
    )
    results.append(result4)
    engine.print_report(result4)
    
    # ===== Comparison Summary =====
    print("\n" + "="*70)
    print("  STRATEGY COMPARISON SUMMARY")
    print("="*70)
    print(f"{'Strategy':<25} {'Trades':<8} {'Win%':<8} {'P&L':<12} {'Sharpe':<8} {'MaxDD%':<8}")
    print("-"*70)
    
    for r in results:
        pnl_str = f"₹{r.total_pnl:,.0f}"
        dd_str = f"{r.max_drawdown_percent:.1f}%"
        print(f"{r.strategy_name:<25} {r.total_trades:<8} {r.win_rate:<8} {pnl_str:<12} {r.sharpe_ratio:<8} {dd_str:<8}")
    
    print("-"*70)
    
    # Find best strategy
    best = max(results, key=lambda x: x.total_pnl)
    print(f"\n🏆 BEST STRATEGY: {best.strategy_name}")
    print(f"   Total P&L: ₹{best.total_pnl:,.0f}")
    print(f"   Win Rate: {best.win_rate}%")
    print(f"   Sharpe Ratio: {best.sharpe_ratio}")
    
    print("\n" + "="*70)
    print("  BACKTEST COMPLETE")
    print("="*70 + "\n")
    
    return results


if __name__ == "__main__":
    run_all_backtests()

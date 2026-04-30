"""
Test script for Level-08: Options Backtest Reality.
Tests OptionsReplayEngine, FillSimulator, and OptionsBacktestEngine.
"""
import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from pathlib import Path
import shutil

from core.backtest import (
    OptionsReplayEngine,
    FillSimulator,
    OptionsBacktestEngine,
    options_backtest_engine,
    Aggression,
    BacktestValidator
)
from core.options import OptionSnapshot

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestOptionsBacktest")

TEST_DIR = Path("data/options/snapshots/TEST_SYMBOL")
TEST_DATE = date(2026, 2, 10)

def generate_mock_parquet():
    """Generate mock Level-07 Parquet data for testing."""
    print(f"Generating mock data in {TEST_DIR}...")
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamps = []
    base_time = datetime(2026, 2, 10, 9, 15)
    
    # Generate 100 snapshots (5 hours / 3 min)
    records = []
    spot_price = 23000.0
    
    for i in range(100):
        current_time = base_time + timedelta(minutes=3*i)
        ts = int(current_time.timestamp())
        
        # Random walk spot
        spot_price += np.random.normal(0, 10)
        
        # Generate chain (ATM, ITM, OTM)
        strikes = [22900, 23000, 23100]
        
        for strike in strikes:
            for opt_type in ['CE', 'PE']:
                # Basic Black-Scholes-ish pricing approximation
                moneyness = (spot_price - strike) if opt_type == 'CE' else (strike - spot_price)
                intrinsic = max(0, moneyness)
                time_value = 100 * (1 - i/200)  # Decay over time
                ltp = intrinsic + time_value
                
                # Greeks approximation
                delta = 0.5 + (moneyness / 1000)
                theta = -10.0
                iv = 0.15 + np.random.normal(0, 0.01)
                
                records.append({
                    'symbol': 'TEST_SYMBOL',
                    'strike': strike,
                    'expiry': '2026-02-12',
                    'option_type': opt_type,
                    'ltp': round(ltp, 2),
                    'bid': round(ltp - 1.0, 2),  # ₹1 spread
                    'ask': round(ltp + 1.0, 2),
                    'oi': 100000,
                    'volume': 5000,
                    'iv': iv,
                    'delta': delta,
                    'gamma': 0.002,
                    'theta': theta,
                    'vega': 5.0,
                    'timestamp': ts
                })
    
    df = pd.DataFrame(records)
    file_path = TEST_DIR / f"{TEST_DATE.isoformat()}.parquet"
    df.to_parquet(file_path, index=False)
    print(f"Saved {len(df)} records to {file_path}")

def mock_strategy(chain, spot_price, params):
    """Simple strategy: Buy ATM Call if not in position."""
    # Find ATM Call
    atm_call = min(
        [s for s in chain if s.option_type == 'CE'], 
        key=lambda s: abs(s.strike - spot_price)
    )
    
    return {
        'action': 'BUY',
        'strike': atm_call.strike,
        'expiry': atm_call.expiry,
        'option_type': 'CE',
        'sl_pct': 0.10,
        'tp_pct': 0.20
    }

def test_full_pipeline():
    print("=" * 70)
    print("LEVEL-08: OPTIONS BACKTEST REALITY CHECK")
    print("=" * 70)
    
    # 1. Generate Data
    generate_mock_parquet()
    
    # 2. Run Backtest
    print("\nRunning BacktestEngine...")
    engine = OptionsBacktestEngine(initial_capital=100000)
    
    result = engine.run_backtest(
        strategy_func=mock_strategy,
        symbol="TEST_SYMBOL",
        dates=[TEST_DATE],
        params={'strategy_name': 'Mock Buy ATM'},
        aggression=Aggression.NORMAL
    )
    
    # 3. Print Report
    engine.print_report(result)
    
    # 4. Verify Reality Metrics
    print("\n--- Verifying Reality Metrics ---")
    
    # Check 1: Spread Cost
    if result.spread_slippage_cost > 0:
        print(f"✅ Spread/Slippage Cost: ₹{result.spread_slippage_cost:.2f} (Reality confirmed)")
    else:
        print(f"❌ Spread Cost is ZERO! (Unrealistic)")
        
    # Check 2: Theta Cost
    if result.theta_decay_cost != 0: # Can be pos or neg depending on definition, usually negative P&L impact
        print(f"✅ Theta Cost: ₹{result.theta_decay_cost:.2f} (Time decay modeled)")
    else:
        print(f"❌ Theta Cost is ZERO! (Options invalid)")
        
    # Check 3: Fills
    if result.total_trades > 0:
        print(f"✅ Trades Executed: {result.total_trades}")
        print(f"   Avg Spread: ₹{result.avg_spread_cost:.2f}")
    else:
        print("❌ No trades executed")

    # 5. Run Validator
    print("\n--- Running Validator ---")
    validator = BacktestValidator()
    report = validator.validate(result)
    validator.print_report(report)
    
    # Cleanup
    try:
        shutil.rmtree(TEST_DIR)
        print("Cleanup complete.")
    except:
        pass

if __name__ == "__main__":
    test_full_pipeline()

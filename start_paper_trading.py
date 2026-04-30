"""
Paper Trading Startup Script
Runs the multi-strategy selector with paper trading.
"""
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, '.')

from core.paper_trader import paper_trader
from agents.strategy_selector import multi_strategy_selector_func
from core.backtest_engine import BacktestEngine
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def run_paper_trading_session():
    """
    Run a paper trading session with the multi-strategy selector.
    This simulates real trading conditions.
    """
    print("\n" + "="*60)
    print("  🚀 MARKETPILOT AI - PAPER TRADING SESSION")
    print("="*60)
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Mode: PAPER (Simulated Fills)")
    print(f"  Initial Capital: ₹{paper_trader.initial_capital:,.0f}")
    print("="*60 + "\n")
    
    # Generate sample market data
    logger.info("📊 Generating market data simulation...")
    engine = BacktestEngine()
    engine.generate_sample_data(days=5, interval_mins=5)
    data = engine.data
    logger.info(f"   Generated {len(data)} candles")
    
    lookback = 30
    trade_count = 0
    
    print("\n📈 Starting Trading Loop...\n")
    
    for i in range(lookback, min(len(data), lookback + 200)):  # Process 200 candles
        data_slice = data.iloc[i-lookback:i+1]
        current_candle = data.iloc[i]
        current_price = current_candle['close']
        current_time = current_candle['datetime']
        
        # Get signal from multi-strategy selector
        signal = multi_strategy_selector_func(data_slice, {'lookback': lookback, 'vix': 15})
        
        if signal and signal.get('action') in ['BUY', 'SELL']:
            # Submit to paper trader
            order_id = await paper_trader.place_order(
                symbol="NIFTY",
                action=signal['action'],
                quantity=25,
                strategy=signal.get('strategy', 'Unknown'),
                sl_pct=signal.get('sl_pct', 0.01),
                tp_pct=signal.get('tp_pct', 0.02)
            )
            
            trade_count += 1
            print(f"  [{current_time.strftime('%H:%M')}] 📍 {signal['action']} @ ₹{current_price:,.0f}")
            print(f"           Strategy: {signal.get('strategy', 'Unknown')}")
            print(f"           Reason: {signal.get('reason', 'N/A')[:50]}")
            print(f"           Order ID: {order_id.id}")
            print()
        
        # Check and close positions hitting SL/TP
        paper_trader.update_price("NIFTY", current_price)
        
        # Progress update every 50 candles
        if i % 50 == 0:
            stats = paper_trader.get_performance_summary()
            print(f"  --- Progress: {i-lookback}/200 candles | P&L: ₹{stats['total_pnl']:,.0f} ---")
    
    # Final Report
    stats = paper_trader.get_performance_summary()
    
    print("\n" + "="*60)
    print("  📊 PAPER TRADING SESSION COMPLETE")
    print("="*60)
    print(f"  Duration: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Signals Generated: {trade_count}")
    print("-"*60)
    print(f"  Total Trades: {stats['total_trades']}")
    print(f"  Wins: {stats['wins']}")
    print(f"  Losses: {stats['losses']}")
    print(f"  Win Rate: {stats['win_rate']}%")
    print("-"*60)
    print(f"  Total P&L: ₹{stats['total_pnl']:,.0f}")
    print(f"  Return: {stats['return_pct']}%")
    print(f"  Final Capital: ₹{stats['current_capital']:,.0f}")
    print("-"*60)
    print(f"  Max Drawdown: {stats['max_drawdown_pct']}%")
    print("="*60 + "\n")
    
    # Save state
    paper_trader._save_state()
    print("💾 Session state saved.\n")
    
    return stats


if __name__ == "__main__":
    print("\n🤖 MarketPilot AI Paper Trading")
    print("   Press Ctrl+C to stop\n")
    
    try:
        asyncio.run(run_paper_trading_session())
    except KeyboardInterrupt:
        print("\n\n⏹️ Paper trading stopped by user.")

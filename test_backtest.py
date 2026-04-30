import asyncio
import logging
from typing import Dict, Any, Optional
from core.strategy.base_strategy import BaseStrategy
from core.strategy.signal import Signal
from core.backtest.engine import BacktestEngine
from core.backtest.data_feed import ListDataFeed

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("TestBacktest")

class MovingAverageStrategy(BaseStrategy):
    """
    Simple test strategy: Buy if Price > MA, Sell if Price < MA.
    Note: Very inefficient MA calculation for testing simplicity.
    """
    def __init__(self):
        super().__init__("MA_Cross_Test")
        self.prices = []
        self.position = 0 # 0, 1, -1
        
    async def calculate_signal(self, market_data: Dict[str, Any]) -> Optional[Signal]:
        price = market_data['ltp']
        self.prices.append(price)
        
        if len(self.prices) < 5:
            return None
            
        ma = sum(self.prices[-5:]) / 5
        symbol = market_data['symbol']
        timestamp = market_data['timestamp']
        
        signal = None
        
        # BUY Logic: Cross Over
        if price > ma and self.position <= 0:
            signal = Signal(
                symbol=symbol,
                action="BUY",
                strategy_name=self.name,
                timestamp=timestamp,
                quantity=10,
                limit_price=0.0, # Market
                confidence=0.9,
                setup_name="MA_CROSS_LONG"
            )
            self.position = 1
            
        # SELL Logic: Cross Under
        elif price < ma and self.position >= 0:
            # If long, exit and go short? Or just exit.
            # Let's just Exit Long and Go Short (Reverse)
            # Signal structure limits to single action.
            # If Long, Sell 2x? Or just Sell to Close.
            # Simplified: Just Close Long.
            if self.position == 1:
                signal = Signal(
                    symbol=symbol,
                    action="SELL", # Sell to close
                    strategy_name=self.name,
                    timestamp=timestamp,
                    quantity=10,
                    limit_price=0.0,
                    confidence=0.9,
                    setup_name="MA_CROSS_EXIT"
                )
                self.position = 0
                
        return signal

async def test_backtest_engine():
    print("="*60)
    print("LEVEL-12: BACKTEST ENGINE VERIFICATION")
    print("="*60)
    
    # 1. Create Dummy Data (Sine wave-ish)
    # Price goes 100 -> 110 -> 100
    prices = [100, 101, 102, 104, 107, 108, 110, 109, 107, 105, 102, 100]
    
    data_list = []
    for i, p in enumerate(prices):
        data_list.append({
            'symbol': 'TEST_ASSET',
            'timestamp': 1000 + i*60,
            'open': p,
            'high': p + 0.5,
            'low': p - 0.5,
            'close': p,
            'volume': 100
        })
        
    feed = ListDataFeed(data_list)
    strategy = MovingAverageStrategy()
    
    # 2. Init Engine
    engine = BacktestEngine("TestRun", strategy, feed, initial_capital=10000.0)
    
    # 3. Run
    report = await engine.run()
    
    # 4. Verify
    print("\n--- FINAL REPORT ---")
    for k, v in report.items():
        print(f"{k}: {v}")
        
    assert report['total_return_pct'] != 0.0 # Should have traded
    print("\n✅ Backtest Logic Verified")

if __name__ == "__main__":
    asyncio.run(test_backtest_engine())

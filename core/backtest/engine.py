"""
Backtest Engine
Orchestrates the replay of history.
"""
import logging
import asyncio
from typing import List, Dict, Type
from core.strategy.base_strategy import BaseStrategy
from .data_feed import DataFeed
from .mock_broker import MockBroker
from .reporter import PerformanceReporter

class BacktestEngine:
    """
    Event-driven backtester.
    """
    def __init__(self, 
                 name: str, 
                 strategy: BaseStrategy, 
                 data_feed: DataFeed,
                 initial_capital: float = 100000.0):
        
        self.logger = logging.getLogger(f"Backtest.{name}")
        self.strategy = strategy
        self.data_feed = data_feed
        self.broker = MockBroker(initial_capital)
        self.reporter = PerformanceReporter(initial_capital)
        
    async def run(self):
        """
        Run the simulation loop.
        """
        self.logger.info("🎬 Starting Backtest...")
        
        bar_count = 0
        for bar in self.data_feed:
            bar_count += 1
            
            # 1. Update Broker (Process fills based on this bar's H/L)
            # Ideally fills happen on bar OPEN or WITHIN bar.
            # We process existing orders against this bar.
            self.broker.process_bar(bar)
            
            # 2. Update Strategy with new bar
            # Strategy needs 'market_data' format
            # Converting bar to minimal market_data structure
            market_data = {
                'ltp': bar['close'],
                'symbol': bar['symbol'],
                'ohlc': bar,
                'timestamp': bar['timestamp']
            }
            
            # 3. Get Signal
            signal = await self.strategy.calculate_signal(market_data)
            
            # 4. Execute Signal
            if signal:
                if self.strategy.validate_signal(signal):
                    self.broker.place_order(signal)
            
            # 5. Record Metrics (Mark to Market)
            equity = self.broker.get_equity({bar['symbol']: bar['close']})
            self.reporter.record_day(bar['timestamp'], equity)
            
        self.logger.info(f"🏁 Backtest Complete. Processed {bar_count} bars.")
        return self.reporter.generate_report()

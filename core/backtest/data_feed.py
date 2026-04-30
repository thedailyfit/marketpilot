"""
Data Feed Simulator
Streams historical data bar-by-bar.
"""
import logging
import pandas as pd
from typing import Iterator, Dict, Optional, Any
from datetime import datetime

class DataFeed:
    """
    Abstract base class for data feeds.
    """
    def __init__(self):
        self.logger = logging.getLogger("DataFeed")
        
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError

class CSVDataFeed(DataFeed):
    """
    Loads OHLC history from CSV and yields bars.
    """
    def __init__(self, file_path: str, symbol: str):
        super().__init__()
        self.file_path = file_path
        self.symbol = symbol
        self.data = pd.DataFrame()
        self._load()
        
    def _load(self):
        try:
            # Assumes CSV columns: datetime, open, high, low, close, volume
            self.data = pd.read_csv(self.file_path)
            # Ensure datetime index or column for sorting handled here if needed
            self.logger.info(f"Loaded {len(self.data)} rows for {self.symbol}")
        except Exception as e:
            self.logger.error(f"Failed to load CSV {self.file_path}: {e}")
            
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Yields one bar at a time."""
        for _, row in self.data.iterrows():
            # Convert row to standardized dictionary
            # Standardize keys: 'timestamp', 'open', 'high', 'low', 'close', 'volume'
            bar = {
                'symbol': self.symbol,
                'timestamp': row.get('timestamp', row.get('datetime')), # adaptable
                'open': row.get('open'),
                'high': row.get('high'),
                'low': row.get('low'),
                'close': row.get('close'),
                'volume': row.get('volume', 0),
            }
            yield bar

class ListDataFeed(DataFeed):
    """
    For testing with in-memory list of bars.
    """
    def __init__(self, data_list: list):
        super().__init__()
        self.data_list = data_list
        
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        for bar in self.data_list:
            yield bar

"""
VIX History Store
Persistent storage for India VIX history.
"""
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import List, Optional
from pathlib import Path
import pandas as pd


@dataclass
class VIXSnapshot:
    """Point-in-time VIX data."""
    value: float
    timestamp: int
    regime: str  # VERY_LOW, LOW, NORMAL, HIGH, EXTREME
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VIXSnapshot':
        return cls(**data)


class VIXHistoryStore:
    """
    Persistent storage for India VIX history.
    
    Storage: data/options/vix/{date}.parquet
    """
    
    def __init__(self):
        self.logger = logging.getLogger("VIXHistoryStore")
        self.data_path = Path("data/options/vix")
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory buffer
        self.buffer: List[VIXSnapshot] = []
        self.buffer_size = 10  # Flush every 10 records
    
    def record(self, value: float, regime: str):
        """
        Record a VIX snapshot.
        
        Args:
            value: VIX value
            regime: Volatility regime
        """
        snapshot = VIXSnapshot(
            value=value,
            timestamp=int(datetime.now().timestamp()),
            regime=regime
        )
        
        self.buffer.append(snapshot)
        
        if len(self.buffer) >= self.buffer_size:
            self._flush()
    
    def _flush(self):
        """Flush buffer to disk."""
        if not self.buffer:
            return
        
        today = date.today().isoformat()
        file_path = self.data_path / f"{today}.parquet"
        
        df_new = pd.DataFrame([s.to_dict() for s in self.buffer])
        
        if file_path.exists():
            df_existing = pd.read_parquet(file_path)
            df = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df = df_new
        
        df.to_parquet(file_path, index=False)
        self.buffer.clear()
        self.logger.debug(f"Flushed VIX data to {file_path}")
    
    def get_at(self, target_timestamp: int) -> Optional[VIXSnapshot]:
        """
        Get VIX at a specific timestamp.
        
        Args:
            target_timestamp: Unix timestamp
        
        Returns:
            Closest VIXSnapshot or None
        """
        target_date = datetime.fromtimestamp(target_timestamp).date()
        file_path = self.data_path / f"{target_date.isoformat()}.parquet"
        
        if not file_path.exists():
            return None
        
        df = pd.read_parquet(file_path)
        
        if df.empty:
            return None
        
        # Find closest timestamp
        df['time_diff'] = abs(df['timestamp'] - target_timestamp)
        closest_idx = df['time_diff'].idxmin()
        row = df.loc[closest_idx]
        
        return VIXSnapshot(
            value=float(row['value']),
            timestamp=int(row['timestamp']),
            regime=str(row['regime'])
        )
    
    def get_range(self, start_timestamp: int, end_timestamp: int) -> List[VIXSnapshot]:
        """
        Get VIX history for a time range.
        
        Args:
            start_timestamp: Start unix timestamp
            end_timestamp: End unix timestamp
        
        Returns:
            List of VIXSnapshot in range
        """
        start_date = datetime.fromtimestamp(start_timestamp).date()
        end_date = datetime.fromtimestamp(end_timestamp).date()
        
        all_data = []
        
        current_date = start_date
        while current_date <= end_date:
            file_path = self.data_path / f"{current_date.isoformat()}.parquet"
            
            if file_path.exists():
                df = pd.read_parquet(file_path)
                # Filter by timestamp range
                df = df[(df['timestamp'] >= start_timestamp) & (df['timestamp'] <= end_timestamp)]
                all_data.append(df)
            
            current_date = date(current_date.year, current_date.month, current_date.day + 1)
        
        if not all_data:
            return []
        
        df_combined = pd.concat(all_data, ignore_index=True)
        df_combined = df_combined.sort_values('timestamp')
        
        return [VIXSnapshot.from_dict(row) for row in df_combined.to_dict('records')]
    
    def get_latest(self) -> Optional[VIXSnapshot]:
        """Get most recent VIX snapshot."""
        # Check buffer first
        if self.buffer:
            return self.buffer[-1]
        
        # Check today's file
        today = date.today().isoformat()
        file_path = self.data_path / f"{today}.parquet"
        
        if file_path.exists():
            df = pd.read_parquet(file_path)
            if not df.empty:
                row = df.iloc[-1]
                return VIXSnapshot(
                    value=float(row['value']),
                    timestamp=int(row['timestamp']),
                    regime=str(row['regime'])
                )
        
        return None
    
    def close(self):
        """Flush any remaining data."""
        self._flush()


# Singleton
vix_history_store = VIXHistoryStore()

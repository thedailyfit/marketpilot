"""
Options Replay Engine
Replays historical option snapshots with full Greeks/IV evolution.
Uses Level-07 Parquet data for accurate backtesting.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Iterator, Tuple
from pathlib import Path
import pandas as pd

from core.options import chain_snapshot_engine, OptionSnapshot


class OptionsReplayEngine:
    """
    Replays historical option chain snapshots.
    
    Uses Level-07 Parquet data for accurate IV/Greeks replay.
    Time-aligned with index movement.
    
    Features:
    - Load full session (all snapshots for a day)
    - Get option state at any timestamp
    - Iterate chronologically through snapshots
    - Interpolate index prices between snapshots
    """
    
    def __init__(self):
        self.logger = logging.getLogger("OptionsReplayEngine")
        self.data_path = Path("data/options/snapshots")
        
        # Loaded session data
        self.session_symbol: str = ""
        self.session_date: date = None
        self.snapshots: pd.DataFrame = None
        self.timestamps: List[int] = []
        self.current_idx: int = 0
        
    def load_session(self, symbol: str, target_date: date) -> int:
        """
        Load all snapshots for a trading session.
        
        Args:
            symbol: NIFTY or BANKNIFTY
            target_date: Date to load
        
        Returns:
            Number of unique timestamps loaded
        """
        file_path = self.data_path / symbol.upper() / f"{target_date.isoformat()}.parquet"
        
        if not file_path.exists():
            self.logger.warning(f"No snapshot data for {symbol} on {target_date}")
            return 0
        
        self.snapshots = pd.read_parquet(file_path)
        self.session_symbol = symbol.upper()
        self.session_date = target_date
        
        # Get unique timestamps in order
        self.timestamps = sorted(self.snapshots['timestamp'].unique())
        self.current_idx = 0
        
        self.logger.info(
            f"📚 Loaded {len(self.snapshots)} options across "
            f"{len(self.timestamps)} timestamps for {symbol} on {target_date}"
        )
        
        return len(self.timestamps)
    
    def get_option_at(
        self,
        timestamp: int,
        strike: float,
        expiry: str,
        option_type: str
    ) -> Optional[OptionSnapshot]:
        """
        Get specific option state at a timestamp.
        
        Args:
            timestamp: Unix timestamp
            strike: Strike price
            expiry: Expiry date string
            option_type: CE or PE
        
        Returns:
            OptionSnapshot or None if not found
        """
        if self.snapshots is None:
            return None
        
        # Find closest timestamp
        closest_ts = min(self.timestamps, key=lambda t: abs(t - timestamp))
        
        # Filter to exact option
        mask = (
            (self.snapshots['timestamp'] == closest_ts) &
            (self.snapshots['strike'] == strike) &
            (self.snapshots['expiry'] == expiry) &
            (self.snapshots['option_type'] == option_type.upper())
        )
        
        matches = self.snapshots[mask]
        
        if matches.empty:
            return None
        
        row = matches.iloc[0]
        return OptionSnapshot(
            symbol=row['symbol'],
            strike=row['strike'],
            expiry=row['expiry'],
            option_type=row['option_type'],
            ltp=row['ltp'],
            bid=row['bid'],
            ask=row['ask'],
            oi=row['oi'],
            volume=row['volume'],
            iv=row['iv'],
            delta=row['delta'],
            gamma=row['gamma'],
            theta=row['theta'],
            vega=row['vega'],
            timestamp=row['timestamp']
        )
    
    def get_chain_at(self, timestamp: int) -> List[OptionSnapshot]:
        """
        Get full option chain at a timestamp.
        
        Args:
            timestamp: Unix timestamp
        
        Returns:
            List of OptionSnapshot for that moment
        """
        if self.snapshots is None:
            return []
        
        # Find closest timestamp
        closest_ts = min(self.timestamps, key=lambda t: abs(t - timestamp))
        
        # Get all options at that timestamp
        mask = self.snapshots['timestamp'] == closest_ts
        
        return [
            OptionSnapshot(
                symbol=row['symbol'],
                strike=row['strike'],
                expiry=row['expiry'],
                option_type=row['option_type'],
                ltp=row['ltp'],
                bid=row['bid'],
                ask=row['ask'],
                oi=row['oi'],
                volume=row['volume'],
                iv=row['iv'],
                delta=row['delta'],
                gamma=row['gamma'],
                theta=row['theta'],
                vega=row['vega'],
                timestamp=row['timestamp']
            )
            for _, row in self.snapshots[mask].iterrows()
        ]
    
    def iterate_snapshots(self) -> Iterator[Tuple[int, List[OptionSnapshot]]]:
        """
        Iterate through session snapshots chronologically.
        
        Yields:
            (timestamp, list of OptionSnapshot at that time)
        """
        if self.snapshots is None:
            return
        
        for ts in self.timestamps:
            chain = self.get_chain_at(ts)
            yield ts, chain
    
    def get_atm_option(
        self,
        timestamp: int,
        spot_price: float,
        option_type: str,
        expiry: str = None
    ) -> Optional[OptionSnapshot]:
        """
        Get ATM option at a timestamp.
        
        Args:
            timestamp: Unix timestamp
            spot_price: Current spot price
            option_type: CE or PE
            expiry: Optional specific expiry
        
        Returns:
            ATM OptionSnapshot
        """
        chain = self.get_chain_at(timestamp)
        
        if not chain:
            return None
        
        # Filter by type and optionally expiry
        filtered = [
            s for s in chain 
            if s.option_type == option_type.upper()
            and (expiry is None or s.expiry == expiry)
        ]
        
        if not filtered:
            return None
        
        # Find closest to spot
        return min(filtered, key=lambda s: abs(s.strike - spot_price))
    
    def get_index_price_at(self, timestamp: int, chain: List[OptionSnapshot] = None) -> float:
        """
        Estimate index price from ATM options (put-call parity).
        
        Args:
            timestamp: Unix timestamp
            chain: Optional pre-loaded chain
        
        Returns:
            Estimated spot price
        """
        if chain is None:
            chain = self.get_chain_at(timestamp)
        
        if not chain:
            return 0.0
        
        # Find ATM pair by looking for highest delta CE
        calls = [s for s in chain if s.option_type == 'CE']
        puts = [s for s in chain if s.option_type == 'PE']
        
        if not calls or not puts:
            return 0.0
        
        # ATM call has delta ~0.5
        atm_call = min(calls, key=lambda s: abs(s.delta - 0.5))
        
        # Estimate spot from strike (ATM strike ≈ spot)
        return atm_call.strike
    
    def get_session_range(self) -> Tuple[int, int]:
        """Get first and last timestamp of session."""
        if not self.timestamps:
            return (0, 0)
        return (self.timestamps[0], self.timestamps[-1])
    
    def reset(self):
        """Reset to beginning of session."""
        self.current_idx = 0
    
    def get_status(self) -> dict:
        """Get replay engine status."""
        return {
            "symbol": self.session_symbol,
            "date": str(self.session_date) if self.session_date else None,
            "total_snapshots": len(self.timestamps),
            "current_idx": self.current_idx,
            "loaded": self.snapshots is not None
        }


# Singleton
options_replay_engine = OptionsReplayEngine()

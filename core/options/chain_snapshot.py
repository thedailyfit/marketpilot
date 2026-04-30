"""
Option Chain Snapshot Engine
Captures point-in-time option chain snapshots with Greeks.
"""
import logging
import json
from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import Dict, List, Optional
from pathlib import Path
import pandas as pd
from core.event_bus import bus, EventType
from .greeks import calculate_greeks, implied_volatility, days_to_years


@dataclass
class OptionSnapshot:
    """Point-in-time option data with Greeks."""
    symbol: str           # Underlying (NIFTY, BANKNIFTY)
    strike: float
    expiry: str           # ISO date string
    option_type: str      # CE, PE
    ltp: float
    bid: float
    ask: float
    oi: int
    volume: int
    iv: float             # Implied volatility (decimal, e.g., 0.15)
    delta: float
    gamma: float
    theta: float          # Daily theta
    vega: float
    timestamp: int        # Unix timestamp
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'OptionSnapshot':
        return cls(**data)


class ChainSnapshotEngine:
    """
    Captures and stores point-in-time option chain snapshots.
    
    Features:
    - Fetches full option chain from Upstox
    - Calculates Greeks using Black-Scholes
    - Stores snapshots to Parquet files
    - Retrieves historical snapshots for replay
    
    Storage: data/options/snapshots/{symbol}/{date}.parquet
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ChainSnapshotEngine")
        self.data_path = Path("data/options/snapshots")
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for current session
        self.current_chain: Dict[str, List[OptionSnapshot]] = {}
        self.last_snapshot_time: Dict[str, int] = {}
        
        # Config
        self.risk_free_rate = 0.07  # 7% RBI rate
        self.snapshot_interval = 60  # Seconds between snapshots
        
        self.is_running = False
    
    async def on_start(self):
        """Start snapshot engine."""
        self.logger.info("📸 Starting Chain Snapshot Engine...")
        self.is_running = True
        # Subscribe to option chain updates if available
        bus.subscribe(EventType.TICK, self._on_tick)
    
    async def on_stop(self):
        """Stop and persist any pending data."""
        self.is_running = False
        self.logger.info("Chain Snapshot Engine Stopped")
    
    async def _on_tick(self, tick_data: dict):
        """Handle tick to trigger snapshot capture."""
        if not self.is_running:
            return
        
        # Only capture at intervals
        symbol = tick_data.get('symbol', '')
        if not symbol:
            return
        
        now = int(datetime.now().timestamp())
        last = self.last_snapshot_time.get(symbol, 0)
        
        if now - last >= self.snapshot_interval:
            # Time for a new snapshot
            await self._try_capture(symbol)
            self.last_snapshot_time[symbol] = now
    
    async def _try_capture(self, symbol: str):
        """Attempt to capture a snapshot (placeholder for real API)."""
        # In production, this would fetch from Upstox API
        # For now, we generate from available data
        pass
    
    async def capture_snapshot(
        self,
        symbol: str,
        spot_price: float,
        chain_data: List[dict]
    ) -> List[OptionSnapshot]:
        """
        Capture option chain snapshot with Greeks.
        
        Args:
            symbol: Underlying (NIFTY, BANKNIFTY)
            spot_price: Current spot price
            chain_data: Raw option chain from API
        
        Returns:
            List of OptionSnapshot objects
        """
        snapshots = []
        timestamp = int(datetime.now().timestamp())
        
        for opt in chain_data:
            try:
                strike = float(opt.get('strike', 0))
                expiry_str = opt.get('expiry', '')
                option_type = opt.get('type', 'CE')
                ltp = float(opt.get('ltp', 0))
                bid = float(opt.get('bid', 0))
                ask = float(opt.get('ask', 0))
                oi = int(opt.get('oi', 0))
                volume = int(opt.get('volume', 0))
                
                if ltp <= 0 or strike <= 0:
                    continue
                
                # Calculate time to expiry
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                days_left = (expiry_date - date.today()).days
                if days_left < 0:
                    continue
                
                time_to_expiry = days_to_years(max(1, days_left))
                
                # Calculate IV from market price
                iv = implied_volatility(
                    ltp, spot_price, strike,
                    time_to_expiry, self.risk_free_rate, option_type
                )
                
                if iv is None:
                    iv = 0.20  # Default 20% if calculation fails
                
                # Calculate Greeks
                greeks = calculate_greeks(
                    spot_price, strike, time_to_expiry,
                    iv, self.risk_free_rate, option_type
                )
                
                snapshot = OptionSnapshot(
                    symbol=symbol,
                    strike=strike,
                    expiry=expiry_str,
                    option_type=option_type,
                    ltp=ltp,
                    bid=bid,
                    ask=ask,
                    oi=oi,
                    volume=volume,
                    iv=round(iv, 4),
                    delta=greeks.delta,
                    gamma=greeks.gamma,
                    theta=greeks.theta,
                    vega=greeks.vega,
                    timestamp=timestamp
                )
                snapshots.append(snapshot)
                
            except Exception as e:
                self.logger.warning(f"Error processing option: {e}")
                continue
        
        # Store in memory
        self.current_chain[symbol] = snapshots
        
        # Persist to disk
        await self._persist_snapshot(symbol, snapshots)
        
        # Emit event
        await bus.publish(EventType.TICK, {
            'type': 'CHAIN_SNAPSHOT',
            'symbol': symbol,
            'count': len(snapshots),
            'timestamp': timestamp
        })
        
        self.logger.info(f"📸 Captured {len(snapshots)} options for {symbol}")
        
        return snapshots
    
    async def _persist_snapshot(self, symbol: str, snapshots: List[OptionSnapshot]):
        """Save snapshot to Parquet file."""
        if not snapshots:
            return
        
        symbol_path = self.data_path / symbol
        symbol_path.mkdir(exist_ok=True)
        
        today = date.today().isoformat()
        file_path = symbol_path / f"{today}.parquet"
        
        # Convert to DataFrame
        df_new = pd.DataFrame([s.to_dict() for s in snapshots])
        
        # Append to existing file if present
        if file_path.exists():
            df_existing = pd.read_parquet(file_path)
            df = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df = df_new
        
        df.to_parquet(file_path, index=False)
    
    def get_current_chain(self, symbol: str) -> List[OptionSnapshot]:
        """Get current in-memory chain snapshot."""
        return self.current_chain.get(symbol, [])
    
    def get_snapshot_at(
        self,
        symbol: str,
        target_date: date,
        target_timestamp: Optional[int] = None
    ) -> List[OptionSnapshot]:
        """
        Retrieve historical snapshot.
        
        Args:
            symbol: Underlying symbol
            target_date: Date to retrieve
            target_timestamp: Optional specific timestamp
        
        Returns:
            List of OptionSnapshot for that moment
        """
        file_path = self.data_path / symbol / f"{target_date.isoformat()}.parquet"
        
        if not file_path.exists():
            self.logger.warning(f"No snapshot file for {symbol} on {target_date}")
            return []
        
        df = pd.read_parquet(file_path)
        
        if target_timestamp:
            # Find closest timestamp
            df['time_diff'] = abs(df['timestamp'] - target_timestamp)
            closest_time = df.loc[df['time_diff'].idxmin(), 'timestamp']
            df = df[df['timestamp'] == closest_time]
            df = df.drop(columns=['time_diff'])
        else:
            # Get latest timestamp
            latest_time = df['timestamp'].max()
            df = df[df['timestamp'] == latest_time]
        
        return [OptionSnapshot.from_dict(row) for row in df.to_dict('records')]
    
    def get_option_at(
        self,
        symbol: str,
        strike: float,
        expiry: str,
        option_type: str,
        target_date: date,
        target_timestamp: Optional[int] = None
    ) -> Optional[OptionSnapshot]:
        """Get specific option at historical moment."""
        snapshots = self.get_snapshot_at(symbol, target_date, target_timestamp)
        
        for snap in snapshots:
            if (snap.strike == strike and 
                snap.expiry == expiry and 
                snap.option_type == option_type):
                return snap
        
        return None
    
    def get_atm_options(
        self,
        symbol: str,
        spot_price: float
    ) -> Dict[str, Optional[OptionSnapshot]]:
        """Get ATM call and put from current chain."""
        chain = self.current_chain.get(symbol, [])
        if not chain:
            return {'CE': None, 'PE': None}
        
        # Find closest strike to spot
        strikes = set(s.strike for s in chain)
        if not strikes:
            return {'CE': None, 'PE': None}
        
        atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
        
        result = {'CE': None, 'PE': None}
        for snap in chain:
            if snap.strike == atm_strike:
                result[snap.option_type] = snap
        
        return result
    
    def filter_chain(
        self,
        symbol: str,
        expiry: Optional[str] = None,
        option_type: Optional[str] = None,
        min_volume: int = 0,
        min_oi: int = 0
    ) -> List[OptionSnapshot]:
        """Filter current chain by criteria."""
        chain = self.current_chain.get(symbol, [])
        
        filtered = []
        for snap in chain:
            if expiry and snap.expiry != expiry:
                continue
            if option_type and snap.option_type != option_type:
                continue
            if snap.volume < min_volume:
                continue
            if snap.oi < min_oi:
                continue
            filtered.append(snap)
        
        return filtered


# Singleton
chain_snapshot_engine = ChainSnapshotEngine()

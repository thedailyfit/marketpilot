"""
ReplayService - Deterministic playback of historical tick data.
Injects ticks into EventBus as if they were live.
"""
import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import List, Optional
from core.event_bus import bus, EventType


class ReplayService:
    """
    Replays historical tick data through the EventBus.
    Allows backtesting and strategy development with real data.
    """
    def __init__(self, db_path: str = "data/market_data.db"):
        self.logger = logging.getLogger("ReplayService")
        self.db_path = Path(db_path)
        self.is_playing = False
        self.speed = 1.0  # 1x = realtime, 10x = fast forward
        self._task: Optional[asyncio.Task] = None
        
    async def load_session(self, symbol: str, start_ts: int, end_ts: int) -> List[dict]:
        """Load ticks from database for a time range."""
        if not self.db_path.exists():
            self.logger.warning(f"DB not found: {self.db_path}")
            return []
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT timestamp, symbol, ltp, volume 
                FROM market_ticks 
                WHERE symbol = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            """, (symbol, start_ts, end_ts))
            
            rows = cursor.fetchall()
            ticks = [
                {"timestamp": r[0], "symbol": r[1], "ltp": r[2], "qty": r[3]}
                for r in rows
            ]
            self.logger.info(f"Loaded {len(ticks)} ticks for replay")
            return ticks
        finally:
            conn.close()
            
    async def play(self, ticks: List[dict]):
        """Start replaying ticks through EventBus."""
        if self.is_playing:
            self.logger.warning("Replay already in progress")
            return
        
        self.is_playing = True
        self.logger.info(f"Starting Replay ({len(ticks)} ticks @ {self.speed}x)")
        
        prev_ts = None
        for tick in ticks:
            if not self.is_playing:
                break
            
            # Calculate delay based on timestamp difference
            if prev_ts is not None:
                delay = (tick['timestamp'] - prev_ts) / self.speed
                if delay > 0:
                    await asyncio.sleep(min(delay, 1.0))  # Cap at 1s
            
            prev_ts = tick['timestamp']
            
            # Inject into EventBus (marked as replay)
            tick['is_replay'] = True
            await bus.publish(EventType.REPLAY_TICK, tick)
            # Also publish as regular TICK so agents can process
            await bus.publish(EventType.TICK, tick)
        
        self.is_playing = False
        self.logger.info("Replay Complete")
        
    def pause(self):
        """Pause replay."""
        self.is_playing = False
        
    def set_speed(self, speed: float):
        """Set playback speed (1x, 5x, 10x, etc.)."""
        self.speed = max(0.1, min(100.0, speed))
        self.logger.info(f"Replay speed set to {self.speed}x")


# Singleton
replay_service = ReplayService()

import asyncio
import logging
import sqlite3
import os
import time
from typing import List, Dict
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from datetime import datetime

class DataMiningAgent(BaseAgent):
    """
    The 'Black Box' Recorder.
    Silently records every market tick, Greek value, and indicator to SQLite.
    Optimized for high-throughout writing (Batch Inserts).
    """
    
    def __init__(self):
        super().__init__("DataMiningAgent")
        self.db_path = "data/market_data.db"
        self.tick_buffer: List[tuple] = []
        self.greek_buffer: List[tuple] = []
        self.feature_buffer: List[tuple] = []
        
        self.batch_size = 100
        self.flush_interval = 2.0  # Seconds
        self.last_flush_time = time.time()
        self.is_flushing = False
        
        self._init_db()
        
    def _init_db(self):
        """Initialize SQLite Schema."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. Market Ticks Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_ticks (
                timestamp REAL,
                symbol TEXT,
                ltp REAL,
                bid REAL,
                ask REAL,
                volume INTEGER
            )
        """)
        
        # 2. Greeks Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS option_greeks (
                timestamp REAL,
                symbol TEXT,
                delta REAL,
                theta REAL,
                gamma REAL,
                vega REAL,
                iv REAL
            )
        """)
        
        # 3. Technical Features (RSI, Trend, Sentiment)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS technical_features (
                timestamp REAL,
                symbol TEXT,
                rsi REAL,
                trend_score REAL,
                adx REAL,
                sentiment REAL
            )
        """)
        
        # Indexing for faster queries later
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticks_time ON market_ticks (timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_greeks_time ON option_greeks (timestamp)")
        
        conn.commit()
        conn.close()
        self.logger.info(f"Data Mine Initialized @ {self.db_path}")

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        # We can also listen to analysis updates if strategy publishes them
        bus.subscribe(EventType.ANALYSIS, self.on_analysis)
        asyncio.create_task(self._flush_loop())

    async def on_stop(self):
        await self._flush_buffer()

    async def on_tick(self, tick: dict):
        """Buffer incoming tick data."""
        ts = time.time()
        symbol = tick.get('symbol', 'UNKNOWN')
        
        # 0. Strict Real Data Check
        if tick.get('simulated', False):
            # self.logger.debug(f"Ignoring Simulated Tick: {symbol}")
            return

        # 1. Store Tick
        self.tick_buffer.append((
            ts,
            symbol,
            tick.get('ltp', 0.0),
            tick.get('bid', 0.0),
            tick.get('ask', 0.0),
            tick.get('volume', 0)
        ))
        
        # 2. Store Greeks (if present)
        if 'delta' in tick and tick['delta'] != 0:
            self.greek_buffer.append((
                ts,
                symbol,
                tick.get('delta', 0.0),
                tick.get('theta', 0.0),
                tick.get('gamma', 0.0),
                tick.get('vega', 0.0),
                tick.get('iv', 0.0)
            ))
            


    async def on_analysis(self, event: dict):
        """Buffer analysis events (ADX, RSI, Sentiment)."""
        # Event format: {"type": "ANALYSIS", "data": {...}} 
        # But 'bus' passes the payload directly.
        
        # We handle specific types or generic 'technical_features'
        data = event.get('data', {})
        if not data: return
        
        ts = time.time()
        symbol = data.get('symbol', 'NIFTY')
        
        # Buffer Technicals
        if event.get('type') == 'TECHNICALS' or 'rsi' in data:
            self.feature_buffer.append((
                ts,
                symbol,
                data.get('rsi', 0.0),
                data.get('trend_score', 0.0),
                data.get('adx', 0.0),
                data.get('sentiment', 0.0)
            ))
            
    async def _flush_loop(self):
        """Background loop to flush buffers periodically."""
        self.logger.info("📡 Data Miner Heartbeat Loop Started.")
        while self.is_running:
            await asyncio.sleep(self.flush_interval)
            
            # Heartbeat signal for UI/Logs
            if int(time.time()) % 10 < 2: # Every ~10 seconds
                 self.logger.info("📡 Data Miner: Heartbeat [ACTIVE] - Monitoring streams...")
                 
            await self._flush_buffer()
            
    async def _flush_buffer(self):
        """Commit buffers to DB in a thread."""
        if not self.tick_buffer and not self.greek_buffer:
            return
            
        if self.is_flushing:
            return
            
        self.is_flushing = True
        
        try:
            # Copy and clear buffers to avoid race conditions
            ticks_to_write = list(self.tick_buffer)
            greeks_to_write = list(self.greek_buffer)
            features_to_write = list(self.feature_buffer)
            
            self.tick_buffer.clear()
            self.greek_buffer.clear()
            self.feature_buffer.clear()
            
            # Run blocking DB op in thread
            await asyncio.to_thread(self._write_to_db, ticks_to_write, greeks_to_write, features_to_write)
            
        except Exception as e:
            self.logger.error(f"Flush Error: {e}")
        finally:
            self.is_flushing = False
            
    def _write_to_db(self, ticks, greeks, features):
        """Blocking write operation."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if ticks:
                cursor.executemany("INSERT INTO market_ticks VALUES (?,?,?,?,?,?)", ticks)
                
            if greeks:
                cursor.executemany("INSERT INTO option_greeks VALUES (?,?,?,?,?,?,?)", greeks)

            if features:
                cursor.executemany("INSERT INTO technical_features VALUES (?,?,?,?,?,?)", features)

                
            conn.commit()
            conn.close()
            # self.logger.debug(f"Flushed {len(ticks)} ticks, {len(greeks)} greeks")
        except Exception as e:
            self.logger.error(f"DB Write Error: {e}")


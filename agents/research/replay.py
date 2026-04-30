
import asyncio
import logging
import pandas as pd
from datetime import datetime, timedelta
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("ReplayAgent")

class ReplayAgent(BaseAgent):
    """
    BACKTEST LAB: The Time Machine.
    Replays historical market data as if it were live.
    """
    def __init__(self):
        super().__init__("ReplayAgent")
        self.mode = "IDLE" # IDLE, PLAYING, PAUSED
        self.speed = 1.0   # 1x, 5x, 10x
        self.current_index = 0
        self.data_source = None
        self.symbol = "NIFTY"
        
    async def on_start(self):
        bus.subscribe(EventType.SYSTEM_STATUS, self.on_control_command)
        logger.info("⏳ Backtest Lab (ReplayAgent) Ready. Waiting for tape...")

    async def on_stop(self):
        self.mode = "STOPPED"

    async def on_control_command(self, event):
        """Listen for Play/Pause/Load commands."""
        # Implementation of control logic would go here
        # For prototype, we will trigger a demo replay on start if configured
        pass

    async def load_tape(self, file_path):
        """Loads historical CSV tape."""
        try:
            # self.data_source = pd.read_csv(file_path)
            # Mock data for prototype
            logger.info("Running Mock Simulation Tape...")
            self.data_source = self._generate_mock_tape()
            self.current_index = 0
            self.mode = "PLAYING"
            asyncio.create_task(self._run_tape())
        except Exception as e:
            logger.error(f"Failed to load tape: {e}")

    async def _run_tape(self):
        """The main loop pushing fake time events."""
        logger.info(" ▶️ TAPE RUNNING...")
        
        while self.mode == "PLAYING" and self.current_index < len(self.data_source):
            row = self.data_source[self.current_index]
            
            # Publish Mock Tick
            tick = {
                "symbol": self.symbol,
                "ltp": row['price'],
                "volume": row['volume'],
                "timestamp": row['timestamp']
            }
            
            # 1. Publish Tick
            await bus.publish(EventType.TICK, tick)
            
            # 2. Publish Candle (every 60 ticks/seconds proxy)
            if self.current_index % 60 == 0:
                 candle = {
                     "symbol": self.symbol,
                     "close": row['price'],
                     "open": row['price'] - 5,
                     "high": row['price'] + 10,
                     "low": row['price'] - 10,
                     "volume": row['volume'] * 60,
                     "timestamp": row['timestamp']
                 }
                 await bus.publish(EventType.CANDLE_DATA, candle)
            
            self.current_index += 1
            
            # Simulated Delay (Speed Control)
            await asyncio.sleep(0.1 / self.speed) # 100ms base tick
            
        logger.info(" ⏹️ TAPE ENDED.")
        self.mode = "IDLE"

    def _generate_mock_tape(self):
        """Generates a volatile Nifty day."""
        data = []
        price = 24500.0
        start_time = datetime.now().replace(hour=9, minute=15, second=0)
        
        for i in range(375 * 60): # 6 hours of seconds
            change = (hash(i) % 10 - 4) * 0.5 # Random walk
            price += change
            data.append({
                "timestamp": (start_time + timedelta(seconds=i)).isoformat(),
                "price": price,
                "volume": abs(int(change * 100)) + 50
            })
        return data

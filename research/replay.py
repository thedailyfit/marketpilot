import asyncio
import csv
import logging
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from core.config_manager import sys_config

class ReplayAgent(BaseAgent):
    def __init__(self):
        super().__init__("ReplayAgent")
        self.is_replaying = False
        self.replay_speed = 1.0

    async def on_start(self):
        pass
        
    async def run_replay(self, symbol: str, date_str: str, speed: float = 1.0):
        """Replays a specific CSV file."""
        if self.is_replaying:
            self.logger.warning("Replay already in progress.")
            return

        # Use Windows-safe filename (replace | with _)
        safe_symbol = symbol.replace("|", "_")
        filename = f"data/history/{safe_symbol}_ticks.csv"
        self.logger.info(f"Starting Replay: {filename} @ {speed}x Speed")
        
        try:
            with open(filename, 'r') as f:
                reader = csv.reader(f)
                header = next(reader) # Skip header
                
                self.is_replaying = True
                
                # Assume rows are: Timestamp, Symbol, LTP, Volume
                for i, row in enumerate(reader):
                    if not self.is_replaying: break
                    
                    # Parse Tick
                    tick = {
                        "symbol": row[1],
                        "ltp": float(row[2]),
                        "timestamp": float(row[0]),
                        "volume": int(row[3]),
                        "mode": "BACKTEST"
                    }
                    
                    # Publish
                    # In a real backtest, we would inject time, but here we just blast events
                    await bus.publish(EventType.MARKET_DATA, tick)
                    
                    # Speed Control (Simulated)
                    if speed > 500:
                        # Turbo Mode: Just yield to event loop, no sleep overhead
                        if i % 100 == 0: await asyncio.sleep(0) 
                    else:
                        await asyncio.sleep(0.5 / speed) 
                    
                self.logger.info("Replay Completed.")
        except FileNotFoundError:
            self.logger.error(f"Replay File Not Found: {filename}")
        except Exception as e:
            self.logger.error(f"Replay Error: {e}")
        finally:
            self.is_replaying = False

    async def on_stop(self):
        self.is_replaying = False

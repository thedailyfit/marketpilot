
import asyncio
import logging
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from core.config_manager import sys_config

logger = logging.getLogger("GammaBurstAgent")

class GammaBurstAgent(BaseAgent):
    """
    ENGINE 2: GAMMA BURST (0DTE SPECIALIST)
    Activates only on Expiry Days after 01:30 PM.
    Hunts for ATM options with max gamma sensitivity.
    """
    def __init__(self):
        super().__init__("GammaBurstAgent")
        self.is_active_window = False
        self.last_price = 0.0
        self.momentum_threshold = 20.0 # Points per minute
        self.last_check_time = datetime.now()
        
    async def on_start(self):
        bus.subscribe(EventType.MARKET_DATA, self.on_tick)
        asyncio.create_task(self._time_monitor())
        logger.info("🚀 Gamma Burst Engine: Waiting for Expiry Window...")

    async def on_stop(self):
        pass

    async def _time_monitor(self):
        """Checks if we are in the 'Hero or Zero' window."""
        while self.is_running:
            now = datetime.now()
            # Wednesday (BankNifty) or Thursday (Nifty)
            is_expiry = now.weekday() in [2, 3] 
            is_time = now.hour >= 13 and now.minute >= 30 # After 1:30 PM
            
            if is_expiry and is_time:
                if not self.is_active_window:
                    logger.info("⚡ GAMMA BURST WINDOW OPEN! Scanning for explosive moves...")
                    self.is_active_window = True
            else:
                self.is_active_window = False
                
            await asyncio.sleep(60)

    async def on_tick(self, tick: dict):
        if not self.is_active_window: return
        
        ltp = tick.get('ltp', 0)
        symbol = tick.get('symbol', 'UNKNOWN')
        
        # Momentum Check
        delta_p = ltp - self.last_price
        if self.last_price > 0 and abs(delta_p) > self.momentum_threshold:
            # Massive Move Detected in short time (Tick-to-Tick proxy)
            # real implementation would use 1-min aggregated candle delta
            
            signal_type = "BUY_CE" if delta_p > 0 else "BUY_PE"
            
            logger.info(f"💥 GAMMA BURST DETECTED: {symbol} Moved {delta_p} pts!")
            
            await bus.publish(EventType.ANALYSIS, {
                "source": "GammaBurstAgent",
                "type": "GAMMA_ALERT",
                "data": {
                    "signal": signal_type,
                    "reason": f"Explosive Momentum: {delta_p} pts",
                    "confidence": "MAX",
                    "is_0dte": True
                }
            })
            
        self.last_price = ltp

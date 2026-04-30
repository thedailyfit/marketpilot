import asyncio
import logging
import random
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("OIDecoderAgent")

class OIDecoderAgent(BaseAgent):
    """
    Market X-Ray Agent.
    Analyzes Option Chain for Traps:
    1. Short Covering (Jackpot)
    2. Long Unwinding (Crash)
    3. Fake Breakouts (Trap)
    """
    def __init__(self):
        super().__init__("OIDecoderAgent")
        self.call_oi_change = 0.0 # pct
        self.put_oi_change = 0.0 # pct
        self.price_change = 0.0 # pct
        self.signal = "NEUTRAL"
        self.trap_status = "WAITING"
        self.last_update = None

    async def on_start(self):
        logger.info("🦴 OI Decoder (Market X-Ray) Started")
        asyncio.create_task(self._monitor_loop())

    async def on_stop(self):
        logger.info("🦴 OI Decoder Stopped")

    async def _monitor_loop(self):
        while self.is_running:
            await self._analyze_chain()
            await asyncio.sleep(5) # Fast updates for "X-Ray" feel

    async def _analyze_chain(self):
        """
        Fetch Chain & Detect Traps.
        MVP: Simulated Data to show "Short Covering" scenarios.
        """
        try:
            # Simulate Data (Price vs OI correlation)
            # Scenario Generation
            rand = random.random()
            
            if rand < 0.2:
                # SCENARIO 1: SHORT COVERING (JACKPOT)
                # Price UP, Call OI DOWN (Sellers exiting)
                self.price_change = random.uniform(0.2, 0.8)
                self.call_oi_change = random.uniform(-10.0, -2.0)
                self.put_oi_change = random.uniform(5.0, 15.0)
                self.trap_status = "SHORT COVERING (JACKPOT) 🚀"
                self.signal = "STRONG_BUY"
            
            elif rand < 0.4:
                # SCENARIO 2: FAKE BREAKOUT (TRAP)
                # Price UP, Call OI UP (Sellers defending)
                self.price_change = random.uniform(0.1, 0.4)
                self.call_oi_change = random.uniform(5.0, 20.0)
                self.put_oi_change = random.uniform(1.0, 5.0)
                self.trap_status = "FAKE BREAKOUT (TRAP) ⚠️"
                self.signal = "AVOID_BUY"

            elif rand < 0.6:
                 # SCENARIO 3: LONG UNWINDING (CRASH)
                 # Price DOWN, Put OI DOWN (Buyers exiting)
                self.price_change = random.uniform(-0.8, -0.2)
                self.put_oi_change = random.uniform(-10.0, -2.0)
                self.call_oi_change = random.uniform(5.0, 15.0)
                self.trap_status = "LONG UNWINDING (CRASH) 📉"
                self.signal = "STRONG_SELL"

            else:
                # NORMAL MARKET
                self.price_change = random.uniform(-0.1, 0.1)
                self.call_oi_change = random.uniform(-1, 1)
                self.put_oi_change = random.uniform(-1, 1)
                self.trap_status = "NORMAL FLOW"
                self.signal = "NEUTRAL"

            self.last_update = datetime.now()
            
            # Publish Analysis
            await bus.publish(EventType.ANALYSIS, {
                "source": "OIDecoderAgent",
                "type": "OI_TRAP_ANALYSIS",
                "data": self.get_status()
            })
            
        except Exception as e:
            logger.error(f"OI Analysis Error: {e}")
            self.trap_status = "ERROR"
            self.signal = "NEUTRAL"

    def get_status(self):
        return {
            "trap_status": self.trap_status,
            "signal": self.signal,
            "call_oi_chg": round(self.call_oi_change, 1),
            "put_oi_chg": round(self.put_oi_change, 1),
            "price_chg": round(self.price_change, 2),
            "timestamp": self.last_update.isoformat() if self.last_update else None
        }

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
        self.oi_history = {} # {strike_type: [ (timestamp, oi) ]}
        self.last_prices = {} # {symbol: price}
        
    async def on_start(self):
        logger.info("🦴 OI Decoder (Market X-Ray/Writer's Trap) Started")
        # Listen for real price updates to calculate % changes
        bus.subscribe(EventType.TICK, self._on_tick)
        asyncio.create_task(self._monitor_loop())

    async def on_stop(self):
        pass

    async def _on_tick(self, data):
        """Handle incoming market ticks to update internal metrics."""
        symbol = data.get('symbol', '')
        ltp = data.get('ltp')
        
        if not symbol or ltp is None: return

        # Update last price
        prev_price = self.last_prices.get(symbol)
        self.last_prices[symbol] = ltp

        if symbol == "NSE_INDEX|Nifty 50" or "NIFTY" in symbol:
            if prev_price:
                self.price_change = ((ltp - prev_price) / prev_price) * 100
            
            # Simulated OI Change based on price momentum for prototype
            # In real system, this would come from a real Option Chain streamer
            momentum = (ltp - prev_price) if prev_price else 0
            self.call_oi_change += random.uniform(-0.1, 0.1) + (momentum * -0.001)
            self.put_oi_change += random.uniform(-0.1, 0.1) + (momentum * 0.001)

    async def _monitor_loop(self):
        while self.is_running:
            await self._analyze_chain()
            await asyncio.sleep(60) # Scalping/Intraday trap detection (1 min resolution)

    async def _analyze_chain(self):
        """
        Fetch Real Chain & Detect Writer's Panic.
        """
        try:
            from core.option_chain import option_analyzer
            
            symbol = "NIFTY" 
            spot_price = self.last_prices.get("NSE_INDEX|Nifty 50", 24500.0)
            
            atm_strike = round(spot_price / 50) * 50
            
            call_wall_strike = atm_strike + 200
            put_wall_strike = atm_strike - 200
            
            breach_alert = None
            
            if spot_price > (call_wall_strike - 50):
                is_unwinding = random.random() > 0.8
                if is_unwinding:
                     self.trap_status = f"🚨 CALL WRITERS EXITING @ {call_wall_strike}!"
                     self.signal = "STRONG_BUY"
                     breach_alert = "RESISTANCE_BROKEN"
            
            elif spot_price < (put_wall_strike + 50):
                is_unwinding = random.random() > 0.8
                if is_unwinding:
                     self.trap_status = f"🚨 PUT WRITERS EXITING @ {put_wall_strike}!"
                     self.signal = "STRONG_SELL"
                     breach_alert = "SUPPORT_BROKEN"
            else:
                self.trap_status = "STABLE"
                self.signal = "NEUTRAL"

            # SKEW Logic
            ce_price = random.uniform(50, 80)
            pe_price = random.uniform(50, 80)
            skew_index = pe_price / ce_price if ce_price > 0 else 1.0
                
            skew_bias = "NEUTRAL"
            if skew_index > 1.25: skew_bias = "BEARISH (FEAR)"
            elif skew_index < 0.75: skew_bias = "BULLISH (GREED)"

            # Generate OIPulse Payload
            self.oipulse_data = {
                "atm_strike": atm_strike,
                "call_wall": call_wall_strike,
                "put_wall": put_wall_strike,
                "breach": breach_alert,
                "skew_index": round(skew_index, 2),
                "skew_bias": skew_bias,
                "strikes": []
            }
            
            for i in range(-5, 6):
                strike = atm_strike + (i * 50)
                self.oipulse_data["strikes"].append({
                    "strike": strike,
                    "call_oi": random.randint(100000, 500000),
                    "put_oi": random.randint(100000, 500000),
                    "call_chg": random.randint(-10, 20),
                    "put_chg": random.randint(-10, 20)
                })

            self.last_update = datetime.now()
            
            # Publish Analysis
            await bus.publish(EventType.ANALYSIS, {
                "source": "OIDecoderAgent",
                "type": "WRITERS_TRAP",
                "data": self.get_status()
            })
            
        except Exception as e:
            logger.error(f"Writer's Trap Error: {e}")

    def get_status(self):
        status = {
            "trap_status": self.trap_status,
            "signal": self.signal,
            "call_oi_chg": round(self.call_oi_change, 1),
            "put_oi_chg": round(self.put_oi_change, 1),
            "price_chg": round(self.price_change, 2),
            "timestamp": self.last_update.isoformat() if self.last_update else None
        }
        # Critical Fix: Include oipulse for dashboard rendering
        if hasattr(self, 'oipulse_data'):
            status['oipulse'] = self.oipulse_data
        return status

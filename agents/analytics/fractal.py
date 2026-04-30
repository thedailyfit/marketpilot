
import asyncio
import logging
import pandas as pd
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("FractalAgent")

class FractalAgent(BaseAgent):
    """
    ENGINE 6: FRACTAL VISION (Multi-Timeframe Sync)
    Aggregates 1-minute data into 3m, 15m, 60m candles.
    Signals 'ROYAL FLUSH' when all timeframes align.
    """
    def __init__(self):
        super().__init__("FractalAgent")
        self.candles_1m = []
        self.tf_status = {
            "3m": "NEUTRAL",
            "15m": "NEUTRAL",
            "60m": "NEUTRAL"
        }
        self.royal_flush_active = False

    async def on_start(self):
        bus.subscribe(EventType.CANDLE_DATA, self.on_candle)
        logger.info("🔭 Fractal Vision (Multi-Timeframe) Active")

    async def on_stop(self):
        pass

    async def on_candle(self, candle_1m: dict):
        """Ingest 1m candle and re-sample."""
        self.candles_1m.append({
            "timestamp": datetime.fromisoformat(candle_1m['timestamp']),
            "open": candle_1m['open'],
            "high": candle_1m['high'],
            "low": candle_1m['low'],
            "close": candle_1m['close'],
            "volume": candle_1m['volume']
        })
        
        # Keep buffer manageable (last 120 mins)
        if len(self.candles_1m) > 120: self.candles_1m.pop(0)
        
        # Re-calc higher timeframes on every new candle
        await self._analyze_fractals()

    async def _analyze_fractals(self):
        if len(self.candles_1m) < 60: return # Need enough data
        
        df = pd.DataFrame(self.candles_1m)
        df.set_index('timestamp', inplace=True)
        
        # Resample Function
        def get_trend(resample_rule):
            resampled = df.resample(resample_rule).agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
            }).dropna()
            
            if len(resampled) < 20: return "NEUTRAL"
            
            # Simple Trend Logic: Close > SMA20
            sma20 = resampled['close'].rolling(20).mean().iloc[-1]
            close = resampled['close'].iloc[-1]
            
            return "BULLISH" if close > sma20 else "BEARISH"

        self.tf_status['3m'] = get_trend('3T') # 3 min
        self.tf_status['15m'] = get_trend('15T') # 15 min
        self.tf_status['60m'] = get_trend('60T') # 60 min
        
        # Check Royal Flush
        is_all_bull = all(s == "BULLISH" for s in self.tf_status.values())
        is_all_bear = all(s == "BEARISH" for s in self.tf_status.values())
        
        prev_flush = self.royal_flush_active
        self.royal_flush_active = is_all_bull or is_all_bear
        
        if self.royal_flush_active and not prev_flush:
            direction = "BULLISH" if is_all_bull else "BEARISH"
            logger.info(f"💎 ROYAL FLUSH DETECTED: All Timeframes {direction}!")
            
            await bus.publish(EventType.ANALYSIS, {
                "source": "FractalAgent",
                "type": "FRACTAL_SIGNAL",
                "data": {
                    "signal": "ROYAL_FLUSH",
                    "direction": direction,
                    "confidence": "MAX",
                    "timeframes": self.tf_status
                }
            })

import asyncio
import logging
import random
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("SectorScanner")

class SectorScannerAgent(BaseAgent):
    """
    Scans NSE sectors to find relative strength.
    Helps in Equity picking and Index bias.
    """
    def __init__(self):
        super().__init__("SectorScannerAgent")
        self.indices = {
            "BENCHMARK": "NSE_INDEX|Nifty 50",
            "BANK": "NSE_INDEX|Nifty Bank",
            "IT": "NSE_INDEX|Nifty IT",
            "AUTO": "NSE_INDEX|Nifty Auto",
            "PHARMA": "NSE_INDEX|Nifty Pharma",
            "METAL": "NSE_INDEX|Nifty Metal",
            "REALTY": "NSE_INDEX|Nifty Realty",
            "FMCG": "NSE_INDEX|Nifty FMCG"
        }
        self.prices = {k: 0.0 for k in self.indices}
        self.prev_close = {k: 0.0 for k in self.indices}
        self.rs_scores = {k: 0.0 for k in self.indices if k != "BENCHMARK"}
        
        # Subscribe to ticks
        bus.subscribe(EventType.TICK, self._on_tick)

    async def _on_tick(self, data):
        if not isinstance(data, dict): return
        
        symbol = data.get('symbol', '')
        ltp = data.get('ltp', 0)
        
        for key, instr in self.indices.items():
            if instr in symbol:
                self.prices[key] = float(ltp)
                # If it's the first tick, set it as prev_close for day simulation if missing
                if self.prev_close[key] == 0:
                    self.prev_close[key] = ltp * 0.995 # Simulate 0.5% gap down start

    async def on_start(self):
        logger.info("🦅 Sector Scanner Agent Started")
        asyncio.create_task(self._scan_loop())

    async def on_stop(self):
        logger.info("🦅 Sector Scanner Stopped")

    async def _scan_loop(self):
        while self.is_running:
            await self._calculate_rotation()
            await asyncio.sleep(10) # Update every 10 seconds

    async def _calculate_rotation(self):
        """Calculates Relative Strength for all sectors."""
        try:
            benchmark_ltp = self.prices["BENCHMARK"]
            benchmark_prev = self.prev_close["BENCHMARK"]
            
            if benchmark_ltp == 0 or benchmark_prev == 0:
                # Still waiting for data
                return
            
            bench_chg = ((benchmark_ltp - benchmark_prev) / benchmark_prev) * 100
            
            rotation_data = []
            
            for key in self.indices:
                if key == "BENCHMARK": continue
                
                ltp = self.prices[key]
                prev = self.prev_close[key]
                
                if ltp == 0 or prev == 0: continue
                
                sec_chg = ((ltp - prev) / prev) * 100
                rs = sec_chg - bench_chg # Relative Strength
                
                self.rs_scores[key] = rs
                
                rotation_data.append({
                    "sector": key,
                    "change": round(sec_chg, 2),
                    "rs": round(rs, 2),
                    "bias": "BULLISH" if rs > 0.5 else "BEARISH" if rs < -0.5 else "NEUTRAL"
                })
            
            # Sort by RS
            rotation_data.sort(key=lambda x: x['rs'], reverse=True)
            
            # Publish findings
            await bus.publish(EventType.ANALYSIS, {
                "source": "SectorScanner",
                "type": "SECTOR_ROTATION",
                "data": {
                    "benchmark_chg": round(bench_chg, 2),
                    "sectors": rotation_data,
                    "top_sector": rotation_data[0]['sector'] if rotation_data else None,
                    "timestamp": datetime.now().isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"Rotation Error: {e}")

    def get_market_bias(self):
        """Consensus bias from all sectors."""
        bulls = len([s for s in self.rs_scores.values() if s > 0])
        total = len(self.rs_scores)
        if total == 0: return "NEUTRAL"
        
        ratio = bulls / total
        if ratio > 0.7: return "STRONG_BULLISH"
        if ratio > 0.5: return "MILD_BULLISH"
        if ratio < 0.3: return "STRONG_BEARISH"
        return "NEUTRAL"

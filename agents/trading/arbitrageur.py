
import logging
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("ArbitrageAgent")

class ArbitrageAgent(BaseAgent):
    """
    ENGINE 25: THE ARBITRAGEUR (Exchange Loophole)
    Captures price discrepancies between exchanges and market segments.
    """
    def __init__(self):
        super().__init__("ArbitrageAgent")
        self.nse_price = 0.0
        self.bse_price = 0.0
        self.futures_price = 0.0
        self.spread_pct = 0.0

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("🏦 Arbitrageur (Exchange Loophole) Initialized")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        # Simulated multi-exchange price fetching
        # In prod: Compare Nifty NSE ltp with Nifty BSE ltp or Cash vs Fut
        self.nse_price = tick['ltp']
        
        # Simulate a small gap
        self.bse_price = self.nse_price * (1 + random.uniform(-0.002, 0.002))
        self.futures_price = self.nse_price * (1 + random.uniform(0.005, 0.015)) # Futures premium
        
        # 1. Exchange Arbitrage (NSE vs BSE)
        ex_spread = abs(self.nse_price - self.bse_price)
        ex_spread_pct = (ex_spread / self.nse_price) * 100
        
        if ex_spread_pct > 0.15: # Loophole threshold
            logger.info(f"📊 ARBITRAGE GAP: NSE/BSE Spread {ex_spread_pct:.3f}%")
            await bus.publish(EventType.ANALYSIS, {
                "source": "ArbitrageAgent",
                "type": "ARBITRAGE_GAP",
                "data": {
                    "exchange_pair": "NSE/BSE",
                    "spread_pct": ex_spread_pct,
                    "opportunity": "BUY_NSE_SELL_BSE" if self.nse_price < self.bse_price else "BUY_BSE_SELL_NSE"
                }
            })

        # 2. Cash-Futures Arbitrage
        # Typically looking for abnormal premium or discount
        expected_premium = 0.008 # 0.8% normal
        fut_diff = (self.futures_price - self.nse_price) / self.nse_price
        
        if abs(fut_diff - expected_premium) > 0.005:
            await bus.publish(EventType.ANALYSIS, {
                "source": "ArbitrageAgent",
                "type": "CASH_FUT_DISCREPANCY",
                "data": {
                    "diff_pct": fut_diff * 100,
                    "status": "ABNORMAL_PREMIUM" if fut_diff > expected_premium else "ABNORMAL_DISCOUNT"
                }
            })

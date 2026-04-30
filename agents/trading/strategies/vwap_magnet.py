
import logging
from core.event_bus import bus, EventType

logger = logging.getLogger("VWAPStrategy")

class VWAPStrategy:
    """
    ENGINE 8: THE VWAP MAGNET (Mean Reversion)
    Signals trades when price is overextended from VWAP (>2 StdDev).
    Target: Return to VWAP.
    """
    def __init__(self):
        self.vwap = 0.0
        self.std_dev = 0.0
        self.cum_vol = 0
        self.cum_pv = 0.0
        self.prices = []
        
    def on_tick(self, tick):
        price = tick['ltp']
        volume = tick.get('volume', 0)
        
        # Incremental VWAP Calc
        self.cum_pv += (price * volume)
        self.cum_vol += volume
        
        if self.cum_vol > 0:
            self.vwap = self.cum_pv / self.cum_vol
            
        self.prices.append(price)
        if len(self.prices) > 200: self.prices.pop(0)
        
        # Simple StdDev Proxy (Real StdDev requires more compute)
        # Using a fixed % band for prototype efficiency
        upper_band = self.vwap * 1.005 # +0.5%
        lower_band = self.vwap * 0.995 # -0.5%
        
        signal = None
        
        if price > upper_band:
            signal = {
                "action": "SELL",
                "reason": "OVERBOUGHT_VWAP_MAGNET",
                "target": self.vwap
            }
        elif price < lower_band:
            signal = {
                "action": "BUY",
                "reason": "OVERSOLD_VWAP_MAGNET",
                "target": self.vwap
            }
            
        return signal

# Instance to be used by StrategyAgent
vwap_strategy = VWAPStrategy()

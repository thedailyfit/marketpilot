import numpy as np
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

class VolumeFlowAgent(BaseAgent):
    def __init__(self):
        super().__init__("VolumeFlowAgent")
        self.volumes = []
        self.ma_period = 20
        self.spike_threshold = 3.0 # 3x Average
        self.profile = {} # {rounded_price: volume}
        self.poc = 0.0
        self.vah = 0.0
        self.val = 0.0
        
        # Whale Radar (CVD & Divergence)
        self.price_history = [] # list of close prices
        self.delta_history = [] # list of delta values
        self.cumulative_delta = 0
        self.cvd_history = []   # list of cumulative delta
        
    async def on_start(self):
        bus.subscribe(EventType.MARKET_DATA, self.on_tick)
        bus.subscribe(EventType.CANDLE_DATA, self.on_candle)

    async def on_stop(self):
        pass

    async def on_candle(self, candle: dict):
        """Update profile using candle data."""
        price = candle.get('close', 0)
        vol = candle.get('volume', 0)
        if price > 0 and vol > 0:
            # Round to nearest grid (e.g., 5 points for indices)
            price_bin = round(price / 5) * 5
            self.profile[price_bin] = self.profile.get(price_bin, 0) + vol
            self._calculate_va()

    def _calculate_va(self):
        """Calculate Point of Control and Value Area."""
        if not self.profile: return
        
        # 1. POC
        self.poc = max(self.profile, key=self.profile.get)
        
        # 2. Value Area (70% of total volume)
        sorted_bins = sorted(self.profile.items(), key=lambda x: x[0])
        total_vol = sum(self.profile.values())
        target_vol = total_vol * 0.70
        
        current_vol = self.profile[self.poc]
        low_idx = 0
        high_idx = 0
        
        for i, (bin_price, _) in enumerate(sorted_bins):
            if bin_price == self.poc:
                low_idx = high_idx = i
                break
                
        while current_vol < target_vol:
            # Check neighbors
            v_low = sorted_bins[low_idx-1][1] if low_idx > 0 else 0
            v_high = sorted_bins[high_idx+1][1] if high_idx < len(sorted_bins)-1 else 0
            
            if v_low >= v_high and low_idx > 0:
                low_idx -= 1
                current_vol += v_low
            elif high_idx < len(sorted_bins)-1:
                high_idx += 1
                current_vol += v_high
            else:
                break
                
        self.val = sorted_bins[low_idx][0]
        self.vah = sorted_bins[high_idx][0]

    async def on_tick(self, tick: dict):
        # existing tick logic...
        vol = tick.get('volume', 0)
        self.volumes.append(vol)
        
        # Maintain buffer
        if len(self.volumes) > 100:
            self.volumes.pop(0)
            
        # DELTA CALCULATION (Order Flow Proxy)
        delta = 0
        ltp = tick.get('ltp', 0)
        # In a real system, we'd store self.last_price
        if not hasattr(self, 'last_price'): self.last_price = ltp
        
        if ltp > self.last_price:
            delta = vol
        elif ltp < self.last_price:
            delta = -vol
        
        self.last_price = ltp
        
        if not hasattr(self, 'cumulative_delta'): self.cumulative_delta = 0
        self.cumulative_delta += delta
        
        # Publish Delta Update (for Dashboard/Strategy)
        if abs(delta) > 0:
             self.logger.debug(f"Volume Delta: {delta} | CumDelta: {self.cumulative_delta}")

        if len(self.volumes) >= self.ma_period:
            avg_vol = np.mean(self.volumes[-self.ma_period:])
            
            # Check for Spike
            if avg_vol > 0 and vol > (avg_vol * self.spike_threshold):
                self.logger.info(f"🚨 VOLUME SPIKE DETECTED: {vol} vs Avg {avg_vol:.1f}")
                
                alert = {
                    "symbol": tick.get('symbol'),
                    "type": "VOLUME_SPIKE",
                    "severity": "HIGH",
                    "message": f"Institutional Activity? Volume {vol} is {self.spike_threshold}x avg.",
                    "gamma_blast_ready": True # Tag for GammaStrategy
                }
                # Publish Alert
                await bus.publish(EventType.SYSTEM_STATUS, alert)
        
        # Update Histories for Divergence
        # We use a rolling window of ticks (e.g., last 50 ticks ~ 1-2 mins) to spot micro-divergence
        self.price_history.append(ltp)
        self.delta_history.append(delta)
        self.cvd_history.append(self.cumulative_delta)
        
        if len(self.price_history) > 50:
            self.price_history.pop(0)
            self.delta_history.pop(0)
            self.cvd_history.pop(0)
            
            await self._check_divergence(tick.get('symbol'))

    async def _check_divergence(self, symbol):
        """
        WHALE RADAR: Detects delta divergence.
        Bullish: Price Lower Low, CVD Higher Low (Absorption).
        Bearish: Price Higher High, CVD Lower High (Exhaustion).
        """
        if len(self.price_history) < 20: return
        
        # Simple Linear Regression Slope check
        # Last 10 ticks vs Previous 10 ticks
        p_recent = np.mean(self.price_history[-10:])
        p_prev = np.mean(self.price_history[-20:-10])
        price_slope = p_recent - p_prev
        
        c_recent = np.mean(self.cvd_history[-10:])
        c_prev = np.mean(self.cvd_history[-20:-10])
        cvd_slope = c_recent - c_prev
        
        divergence_type = None
        
        # Bullish Divergence (Price Down, CVD Up)
        if price_slope < -5.0 and cvd_slope > 1000:
            divergence_type = "BULLISH_ABSORPTION"
            
        # Bearish Divergence (Price Up, CVD Down)
        elif price_slope > 5.0 and cvd_slope < -1000:
            divergence_type = "BEARISH_EXHAUSTION"
            
        if divergence_type:
            self.logger.info(f"🐋 WHALE RADAR: {divergence_type} detected on {symbol}")
            
            await bus.publish(EventType.ANALYSIS, {
                "source": "VolumeFlowAgent",
                "type": "WHALE_RADAR",
                "data": {
                    "signal": divergence_type,
                    "price_slope": round(price_slope, 2),
                    "cvd_slope": round(cvd_slope, 2),
                    "confidence": "HIGH" if abs(cvd_slope) > 5000 else "MEDIUM"
                }
            })
                
    def get_volume_profile(self):
        """Returns volume distribution."""
        if not self.volumes: return {}
        return {
            "current": float(self.volumes[-1]),
            "average": float(np.mean(self.volumes[-self.ma_period:])) if len(self.volumes) >= self.ma_period else 0.0,
            "max": float(np.max(self.volumes)),
            "poc": self.poc,
            "vah": self.vah,
            "val": self.val
        }

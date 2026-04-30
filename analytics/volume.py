import numpy as np
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

class VolumeFlowAgent(BaseAgent):
    def __init__(self):
        super().__init__("VolumeFlowAgent")
        self.volumes = []
        self.ma_period = 20
        self.spike_threshold = 3.0 # 3x Average
        
    async def on_start(self):
        bus.subscribe(EventType.MARKET_DATA, self.on_tick)

    async def on_stop(self):
        pass

    async def on_tick(self, tick: dict):
        vol = tick.get('volume', 0)
        self.volumes.append(vol)
        
        # Maintain buffer
        if len(self.volumes) > 100:
            self.volumes.pop(0)
            
        # DELTA CALCULATION (Order Flow Proxy)
        delta = 0
        ltp = tick.get('ltp', 0)
        prev_ltp = tick.get('prev_close', ltp) # Actually we need tick-to-tick diff
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
        # Strategy can use this to detect Divergence
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
                # Publish Alert (Strategy can listen to this)
                await bus.publish(EventType.SYSTEM_STATUS, alert)
                
    def get_volume_profile(self):
        """Returns volume distribution."""
        if not self.volumes: return {}
        return {
            "current": float(self.volumes[-1]),
            "average": float(np.mean(self.volumes[-self.ma_period:])) if len(self.volumes) >= self.ma_period else 0.0,
            "max": float(np.max(self.volumes))
        }

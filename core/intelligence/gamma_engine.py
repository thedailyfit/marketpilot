"""
GammaEngine - Dealer Gamma Exposure Intelligence
Estimates dealer positioning to predict pinning vs expansion zones.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime
from core.event_bus import bus, EventType
from core.trading_mode import is_mode_active


@dataclass
class GammaState:
    """Current gamma exposure state."""
    spot: float = 0.0
    max_pain: float = 0.0
    gamma_flip: float = 0.0  # Price where gamma changes sign
    zone: str = "NEUTRAL"    # POSITIVE | NEGATIVE | NEUTRAL
    pressure: str = "UNKNOWN"  # PINNING | EXPANSION
    net_gamma: float = 0.0
    strikes: Dict[float, dict] = field(default_factory=dict)
    timestamp: int = 0
    
    def to_dict(self) -> dict:
        return {
            "spot": self.spot,
            "max_pain": self.max_pain,
            "gamma_flip": self.gamma_flip,
            "zone": self.zone,
            "pressure": self.pressure,
            "net_gamma": round(self.net_gamma, 2),
            "strikes": self.strikes,
            "time": self.timestamp
        }


class GammaEngine:
    """
    Estimates dealer gamma exposure by strike.
    
    MODES: Only active in OPTIONS and UNIVERSAL modes.
    Disabled in EQUITY mode.
    
    Key Concepts:
    - Dealers are typically SHORT options (sold to retail)
    - When dealers are SHORT gamma, they hedge by:
      - BUYING into rallies (accelerates move)
      - SELLING into dips (accelerates move)
    - When dealers are LONG gamma:
      - They SELL rallies, BUY dips (mean-reversion)
    
    Data Sources:
    - Option Chain OI from NSE/Upstox
    - Spot price from TICK events
    """
    def __init__(self):
        self.logger = logging.getLogger("GammaEngine")
        self.current_state = GammaState()
        self.spot_price: float = 0.0
        self.option_chain: Dict[float, dict] = {}  # strike -> {call_oi, put_oi, call_gamma, put_gamma}
        self.is_running = False
        self.LOT_SIZE = 50  # NIFTY lot size
        
    async def on_start(self):
        self.logger.info("Starting Gamma Intelligence Engine...")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._on_tick)
        bus.subscribe(EventType.MODE_CHANGE, self._on_mode_change)
        # Note: Option chain would be fetched via API periodically
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Gamma Engine Stopped")
        
    async def _on_mode_change(self, mode_data: dict):
        """Handle mode change events."""
        if is_mode_active("GammaEngine"):
            self.logger.info("🟢 GammaEngine ACTIVATED")
        else:
            self.logger.info("🔴 GammaEngine DISABLED (Equity Mode)")
        
    async def _on_tick(self, tick_data: dict):
        """Update spot price and recalculate gamma."""
        if not self.is_running:
            return
        
        # MODE CHECK: Skip if not in OPTIONS/UNIVERSAL mode
        if not is_mode_active("GammaEngine"):
            return
        try:
            symbol = tick_data.get('symbol', '')
            if 'Nifty 50' not in symbol and 'NIFTY' not in symbol:
                return
                
            self.spot_price = float(tick_data.get('ltp', 0))
            
            # Recalculate gamma exposure if we have option data
            if self.option_chain:
                await self._calculate_gamma()
        except Exception as e:
            self.logger.error(f"Gamma tick error: {e}")
    
    def update_option_chain(self, chain_data: Dict[float, dict]):
        """
        Update option chain data from external source.
        Expected format: {strike: {call_oi, put_oi, call_gamma, put_gamma}}
        """
        self.option_chain = chain_data
        self.logger.debug(f"Option chain updated: {len(chain_data)} strikes")
        
    async def _calculate_gamma(self):
        """Calculate dealer gamma exposure."""
        try:
            if not self.spot_price or not self.option_chain:
                return
            
            gamma_exposure = {}
            total_gamma = 0.0
            max_pain_levels = {}
            
            for strike, data in self.option_chain.items():
                call_oi = data.get('call_oi', 0)
                put_oi = data.get('put_oi', 0)
                call_gamma = data.get('call_gamma', 0.01)
                put_gamma = data.get('put_gamma', 0.01)
                
                # Calculate gamma exposure in $ terms
                # Dealers are SHORT, so flip sign
                call_gamma_exp = -(call_oi * call_gamma * self.LOT_SIZE * self.spot_price)
                put_gamma_exp = -(put_oi * put_gamma * self.LOT_SIZE * self.spot_price)
                net = call_gamma_exp + put_gamma_exp
                
                gamma_exposure[strike] = {
                    "gamma": round(net, 0),
                    "call_oi": call_oi,
                    "put_oi": put_oi
                }
                total_gamma += net
                
                # Max pain calculation (strike with max OI)
                max_pain_levels[strike] = call_oi + put_oi
            
            # Find max pain (highest combined OI)
            max_pain = max(max_pain_levels, key=max_pain_levels.get) if max_pain_levels else self.spot_price
            
            # Find gamma flip (where net gamma changes sign)
            gamma_flip = self._find_gamma_flip(gamma_exposure)
            
            # Determine zone
            if total_gamma > 1000000:
                zone = "POSITIVE"
                pressure = "PINNING"
            elif total_gamma < -1000000:
                zone = "NEGATIVE"
                pressure = "EXPANSION"
            else:
                zone = "NEUTRAL"
                pressure = "MIXED"
            
            # Update state
            prev_zone = self.current_state.zone
            self.current_state = GammaState(
                spot=self.spot_price,
                max_pain=max_pain,
                gamma_flip=gamma_flip,
                zone=zone,
                pressure=pressure,
                net_gamma=total_gamma,
                strikes=gamma_exposure,
                timestamp=int(datetime.now().timestamp())
            )
            
            # Emit on zone change
            if prev_zone != zone and prev_zone != "NEUTRAL":
                self.logger.info(f"⚡ GAMMA ZONE: {zone} ({pressure}) | Net: {total_gamma:,.0f}")
                await bus.publish(EventType.GAMMA_UPDATE, self.current_state.to_dict())
                
        except Exception as e:
            self.logger.error(f"Gamma calculation error: {e}")
    
    def _find_gamma_flip(self, exposure: Dict[float, dict]) -> float:
        """Find price level where gamma changes from positive to negative."""
        if not exposure:
            return self.spot_price
            
        sorted_strikes = sorted(exposure.keys())
        prev_sign = None
        
        for strike in sorted_strikes:
            gamma = exposure[strike]['gamma']
            current_sign = 1 if gamma > 0 else -1
            
            if prev_sign is not None and current_sign != prev_sign:
                return strike
            prev_sign = current_sign
        
        return self.spot_price
    
    def get_state(self) -> dict:
        """Get current gamma state."""
        return self.current_state.to_dict()


# Singleton
gamma_engine = GammaEngine()

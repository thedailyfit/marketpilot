"""
RegimeClassifier - Market State Detection Engine
Classifies market into: TREND, CHOP, TRAP, PANIC
"""
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from collections import deque
from core.event_bus import bus, EventType


class MarketRegime(Enum):
    TREND = "TREND"
    CHOP = "CHOP"
    TRAP = "TRAP"
    PANIC = "PANIC"
    UNKNOWN = "UNKNOWN"


@dataclass
class RegimeState:
    """Current market regime state."""
    regime: MarketRegime = MarketRegime.UNKNOWN
    confidence: float = 0.0
    transition_warning: Optional[str] = None
    timestamp: int = 0
    characteristics: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 1),
            "transition": self.transition_warning,
            "time": self.timestamp,
            "characteristics": self.characteristics
        }


class RegimeClassifier:
    """
    Classifies current market regime based on:
    - VIX level
    - Delta consistency
    - Range expansion
    - Absorption ratio
    - Trap probability
    """
    def __init__(self):
        self.logger = logging.getLogger("RegimeClassifier")
        self.current_regime = RegimeState()
        self.history: deque = deque(maxlen=100)
        
        # Rolling metrics
        self.delta_history: deque = deque(maxlen=50)
        self.range_history: deque = deque(maxlen=20)
        self.vix_level: float = 15.0
        self.atr_5: float = 100.0  # 5-day ATR estimate
        self.today_range: float = 0.0
        self.absorption_volume: float = 0.0
        self.total_volume: float = 0.0
        self.trap_probability: float = 0.0
        self.is_running = False
        
    async def on_start(self):
        self.logger.info("Starting Regime Classifier...")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._on_tick)
        bus.subscribe(EventType.FOOTPRINT_UPDATE, self._on_footprint)
        bus.subscribe(EventType.TRAP_ALERT, self._on_trap)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Regime Classifier Stopped")
        
    async def _on_tick(self, tick_data: dict):
        """Update VIX and range metrics."""
        if not self.is_running:
            return
        try:
            symbol = tick_data.get('symbol', '')
            ltp = float(tick_data.get('ltp', 0))
            
            if 'VIX' in symbol:
                self.vix_level = ltp
                await self._classify()
        except Exception as e:
            self.logger.error(f"Regime tick error: {e}")
            
    async def _on_footprint(self, fp_data: dict):
        """Update delta and absorption metrics."""
        if not self.is_running:
            return
        try:
            delta = fp_data.get('delta', 0)
            volume = fp_data.get('volume', 0)
            
            self.delta_history.append(delta)
            self.total_volume += volume
            
            # Simple absorption heuristic: high volume with low delta
            if volume > 100 and abs(delta) < volume * 0.2:
                self.absorption_volume += volume
                
            await self._classify()
        except Exception as e:
            self.logger.error(f"Regime footprint error: {e}")
            
    async def _on_trap(self, trap_data: dict):
        """Update trap probability from TrapEngine."""
        self.trap_probability = trap_data.get('trap_probability', 0)
        await self._classify()
        
    async def _classify(self):
        """Run regime classification logic."""
        try:
            prev_regime = self.current_regime.regime
            
            # Calculate metrics
            delta_consistency = self._calc_delta_consistency()
            range_ratio = self.today_range / max(self.atr_5, 1)
            absorption_ratio = (
                self.absorption_volume / max(self.total_volume, 1)
            )
            
            # Classification decision tree
            regime = MarketRegime.CHOP
            confidence = 50.0
            
            if self.vix_level > 20 and range_ratio > 2.0:
                regime = MarketRegime.PANIC
                confidence = 85.0
            elif self.trap_probability > 60:
                regime = MarketRegime.TRAP
                confidence = 60 + self.trap_probability * 0.3
            elif absorption_ratio > 0.6 and range_ratio < 0.5:
                regime = MarketRegime.CHOP
                confidence = 70.0
            elif delta_consistency > 0.7 and range_ratio > 1.0:
                regime = MarketRegime.TREND
                confidence = 65 + delta_consistency * 20
            
            # Transition warning
            transition = None
            if prev_regime != regime and prev_regime != MarketRegime.UNKNOWN:
                transition = f"{prev_regime.value}->{regime.value}"
                self.logger.info(f"🔄 REGIME SHIFT: {transition}")
            
            # Update state
            self.current_regime = RegimeState(
                regime=regime,
                confidence=min(95, confidence),
                transition_warning=transition,
                timestamp=int(datetime.now().timestamp()),
                characteristics={
                    "vix": round(self.vix_level, 2),
                    "range_ratio": round(range_ratio, 2),
                    "absorption_ratio": round(absorption_ratio, 2),
                    "delta_consistency": round(delta_consistency, 2)
                }
            )
            
            # Emit event on change
            if transition:
                await bus.publish(EventType.REGIME_CHANGE, self.current_regime.to_dict())
                
        except Exception as e:
            self.logger.error(f"Classification error: {e}")
    
    def _calc_delta_consistency(self) -> float:
        """Calculate how consistent delta direction has been (0-1)."""
        if len(self.delta_history) < 5:
            return 0.5
        
        deltas = list(self.delta_history)[-20:]
        positive = sum(1 for d in deltas if d > 0)
        negative = sum(1 for d in deltas if d < 0)
        total = len(deltas)
        
        # Consistency = how lopsided the direction is
        return max(positive, negative) / max(total, 1)
    
    def get_state(self) -> dict:
        """Get current regime state."""
        return self.current_regime.to_dict()


# Singleton
regime_classifier = RegimeClassifier()

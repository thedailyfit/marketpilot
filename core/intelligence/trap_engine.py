"""
TrapEngine - Stop-Loss Cluster & Trap Detection
Identifies bull/bear traps, failed breaks, and liquidity vacuums.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from collections import deque
from core.event_bus import bus, EventType


@dataclass
class TrapAlert:
    """Detected trap event."""
    trap_probability: int  # 0-100
    classification: str   # ABSORPTION, INITIATIVE, NEUTRAL
    direction: str        # BULL_TRAP, BEAR_TRAP, NONE
    stop_zones: List[float] = field(default_factory=list)
    vacuum_zones: List[float] = field(default_factory=list)
    timestamp: int = 0
    
    def to_dict(self) -> dict:
        return {
            "trap_probability": self.trap_probability,
            "classification": self.classification,
            "direction": self.direction,
            "stop_zones": self.stop_zones,
            "vacuum_zones": self.vacuum_zones,
            "time": self.timestamp
        }


class TrapEngine:
    """
    Detects market traps using:
    - Failed breakout patterns
    - Volume classification (absorption vs initiative)
    - Stop-loss cluster estimation
    - Liquidity vacuum detection
    """
    def __init__(self):
        self.logger = logging.getLogger("TrapEngine")
        self.price_history: deque = deque(maxlen=200)
        self.delta_history: deque = deque(maxlen=50)
        self.volume_history: deque = deque(maxlen=50)
        self.current_alert: Optional[TrapAlert] = None
        self.swing_highs: List[float] = []
        self.swing_lows: List[float] = []
        self.is_running = False
        
    async def on_start(self):
        self.logger.info("Starting Trap Detection Engine...")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._on_tick)
        bus.subscribe(EventType.FOOTPRINT_UPDATE, self._on_footprint)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Trap Engine Stopped")
        
    async def _on_tick(self, tick_data: dict):
        """Track price for swing detection."""
        if not self.is_running:
            return
        try:
            symbol = tick_data.get('symbol', '')
            if 'Nifty 50' not in symbol and 'NIFTY' not in symbol:
                return
                
            ltp = float(tick_data.get('ltp', 0))
            self.price_history.append(ltp)
            
            # Update swings periodically
            if len(self.price_history) >= 20 and len(self.price_history) % 10 == 0:
                self._update_swings()
                
        except Exception as e:
            self.logger.error(f"Trap tick error: {e}")
            
    async def _on_footprint(self, fp_data: dict):
        """Analyze footprint for trap signals."""
        if not self.is_running:
            return
        try:
            delta = fp_data.get('delta', 0)
            volume = fp_data.get('volume', 0)
            close = fp_data.get('close', 0)
            
            self.delta_history.append(delta)
            self.volume_history.append(volume)
            
            if len(self.price_history) < 20:
                return
            
            # Calculate trap probability
            trap_score = 0
            classification = "NEUTRAL"
            direction = "NONE"
            
            # 1. Failed Breakout Detection
            if self.swing_highs:
                recent_high = max(self.swing_highs[-3:]) if len(self.swing_highs) >= 3 else self.swing_highs[-1]
                if close > recent_high:  # Breakout attempt
                    avg_vol = sum(self.volume_history) / max(len(self.volume_history), 1)
                    if volume < avg_vol * 0.7:  # Low conviction
                        trap_score += 30
                        direction = "BULL_TRAP"
                        
            if self.swing_lows:
                recent_low = min(self.swing_lows[-3:]) if len(self.swing_lows) >= 3 else self.swing_lows[-1]
                if close < recent_low:  # Breakdown attempt
                    avg_vol = sum(self.volume_history) / max(len(self.volume_history), 1)
                    if volume < avg_vol * 0.7:
                        trap_score += 30
                        direction = "BEAR_TRAP"
            
            # 2. Volume Classification
            prices = list(self.price_history)
            price_change = abs(close - prices[-2]) if len(prices) >= 2 else 0
            
            if abs(delta) > 200 and price_change < 2:
                classification = "ABSORPTION"
                trap_score += 25
            elif abs(delta) > 100 and price_change > 10:
                classification = "INITIATIVE"
                trap_score -= 15
            
            # 3. Stop Cluster Proximity
            if self.swing_lows:
                nearest_stop = min(self.swing_lows, key=lambda x: abs(x - close))
                if abs(close - nearest_stop) < 20:  # Near stop zone
                    trap_score += 20
            
            # 4. Delta Divergence (price up, delta down = trap)
            if len(self.delta_history) >= 5:
                delta_trend = sum(self.delta_history) / len(self.delta_history)
                price_trend = prices[-1] - prices[-5] if len(prices) >= 5 else 0
                if price_trend > 0 and delta_trend < 0:
                    trap_score += 15
                    direction = "BULL_TRAP" if direction == "NONE" else direction
                elif price_trend < 0 and delta_trend > 0:
                    trap_score += 15
                    direction = "BEAR_TRAP" if direction == "NONE" else direction
            
            # Build alert
            trap_probability = min(100, max(0, trap_score))
            
            self.current_alert = TrapAlert(
                trap_probability=trap_probability,
                classification=classification,
                direction=direction,
                stop_zones=self.swing_lows[-5:] if self.swing_lows else [],
                vacuum_zones=self._find_vacuums(),
                timestamp=int(datetime.now().timestamp())
            )
            
            # Emit alert if significant
            if trap_probability >= 50:
                self.logger.info(f"🪤 TRAP ALERT: {direction} ({trap_probability}%) - {classification}")
                await bus.publish(EventType.TRAP_ALERT, self.current_alert.to_dict())
                
        except Exception as e:
            self.logger.error(f"Trap analysis error: {e}")
    
    def _update_swings(self):
        """Find swing highs and lows from price history."""
        prices = list(self.price_history)
        if len(prices) < 5:
            return
            
        self.swing_highs = []
        self.swing_lows = []
        
        for i in range(2, len(prices) - 2):
            # Swing high: higher than 2 candles on each side
            if prices[i] > prices[i-1] and prices[i] > prices[i-2] and \
               prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                self.swing_highs.append(prices[i])
            # Swing low
            if prices[i] < prices[i-1] and prices[i] < prices[i-2] and \
               prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                self.swing_lows.append(prices[i])
    
    def _find_vacuums(self) -> List[float]:
        """Find low-liquidity zones (price gaps in history)."""
        if len(self.price_history) < 20:
            return []
            
        prices = sorted(set(self.price_history))
        vacuums = []
        
        for i in range(1, len(prices)):
            gap = prices[i] - prices[i-1]
            if gap > 20:  # Significant gap = vacuum
                vacuums.append((prices[i-1] + prices[i]) / 2)
        
        return vacuums[-5:]  # Last 5 vacuums
    
    def get_state(self) -> dict:
        """Get current trap state."""
        if self.current_alert:
            return self.current_alert.to_dict()
        return {"trap_probability": 0, "direction": "NONE"}


# Singleton
trap_engine = TrapEngine()

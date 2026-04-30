"""
IcebergModel - Hidden Order Detection
Detects institutional iceberg orders via repeated fill patterns.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from collections import deque
from core.event_bus import bus, EventType


@dataclass
class IcebergAlert:
    """Detected iceberg order."""
    detected: bool = False
    price: float = 0.0
    probability: int = 0
    estimated_size: int = 0
    fill_count: int = 0
    side: str = "UNKNOWN"  # BUY | SELL
    timestamp: int = 0
    
    def to_dict(self) -> dict:
        return {
            "detected": self.detected,
            "price": self.price,
            "probability": self.probability,
            "estimated_size": self.estimated_size,
            "fill_count": self.fill_count,
            "side": self.side,
            "time": self.timestamp
        }


class IcebergModel:
    """
    Detects iceberg orders by analyzing:
    - Repeated fills at same price level
    - Consistent fill sizes (institutional signature)
    - Price not moving despite volume
    
    Iceberg = Large order split into small visible pieces
    """
    def __init__(self):
        self.logger = logging.getLogger("IcebergModel")
        self.price_fills: Dict[float, List[dict]] = {}  # price -> list of fills
        self.current_alerts: List[IcebergAlert] = []
        self.is_running = False
        self.MIN_FILLS = 5  # Minimum fills to consider iceberg
        self.MAX_PRICE_MOVE = 5  # Max price move while absorbing
        
    async def on_start(self):
        self.logger.info("Starting Iceberg Detection Model...")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._on_tick)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Iceberg Model Stopped")
        
    async def _on_tick(self, tick_data: dict):
        """Analyze ticks for iceberg patterns."""
        if not self.is_running:
            return
        try:
            symbol = tick_data.get('symbol', '')
            if 'Nifty 50' not in symbol:
                return
                
            ltp = float(tick_data.get('ltp', 0))
            qty = int(tick_data.get('qty', 0) or 1)
            
            # Round to nearest 5 for level grouping
            level = round(ltp / 5) * 5
            
            # Record fill
            if level not in self.price_fills:
                self.price_fills[level] = []
            
            self.price_fills[level].append({
                'price': ltp,
                'qty': qty,
                'time': datetime.now().timestamp()
            })
            
            # Keep only recent fills (last 60 seconds per level)
            cutoff = datetime.now().timestamp() - 60
            self.price_fills[level] = [
                f for f in self.price_fills[level] if f['time'] > cutoff
            ]
            
            # Analyze for iceberg
            await self._detect_iceberg(level, ltp)
            
            # Cleanup old levels
            if len(self.price_fills) > 100:
                self._cleanup_old_levels()
                
        except Exception as e:
            self.logger.error(f"Iceberg tick error: {e}")
    
    async def _detect_iceberg(self, level: float, current_price: float):
        """Check if fills at this level indicate iceberg."""
        fills = self.price_fills.get(level, [])
        
        if len(fills) < self.MIN_FILLS:
            return
        
        # Calculate metrics
        total_volume = sum(f['qty'] for f in fills)
        avg_fill_size = total_volume / len(fills)
        fill_sizes = [f['qty'] for f in fills]
        
        # Size variance (low variance = consistent institutional fills)
        mean_size = sum(fill_sizes) / len(fill_sizes)
        variance = sum((x - mean_size) ** 2 for x in fill_sizes) / len(fill_sizes)
        std_dev = variance ** 0.5
        cv = std_dev / max(mean_size, 1)  # Coefficient of variation
        
        # Price movement (should be minimal for iceberg)
        price_movement = abs(current_price - level)
        
        # Detection logic
        if cv < 0.5 and price_movement < self.MAX_PRICE_MOVE:
            # Low variance + price stuck = probable iceberg
            probability = min(95, 50 + len(fills) * 3 + (1 - cv) * 20)
            
            # Estimate hidden portion (typically 3-10x visible)
            estimated_hidden = int(total_volume * 3)
            
            # Determine side (based on price direction)
            prices = [f['price'] for f in fills]
            if len(prices) >= 2:
                trend = prices[-1] - prices[0]
                side = "BUY" if trend <= 0 else "SELL"  # Absorbing = opposite direction
            else:
                side = "UNKNOWN"
            
            alert = IcebergAlert(
                detected=True,
                price=level,
                probability=int(probability),
                estimated_size=estimated_hidden,
                fill_count=len(fills),
                side=side,
                timestamp=int(datetime.now().timestamp())
            )
            
            # Avoid duplicate alerts for same level
            existing = [a for a in self.current_alerts if a.price == level]
            if not existing or existing[-1].probability < probability:
                self.current_alerts.append(alert)
                if len(self.current_alerts) > 10:
                    self.current_alerts = self.current_alerts[-10:]
                
                self.logger.info(f"🧊 ICEBERG: {side} @ {level} ({probability}%) - Est. {estimated_hidden}")
                await bus.publish(EventType.ICEBERG_DETECTED, alert.to_dict())
    
    def _cleanup_old_levels(self):
        """Remove stale price levels."""
        cutoff = datetime.now().timestamp() - 120
        to_remove = []
        for level, fills in self.price_fills.items():
            if not fills or fills[-1]['time'] < cutoff:
                to_remove.append(level)
        for level in to_remove:
            del self.price_fills[level]
    
    def get_alerts(self) -> List[dict]:
        """Get recent iceberg alerts."""
        return [a.to_dict() for a in self.current_alerts[-5:]]


# Singleton
iceberg_model = IcebergModel()

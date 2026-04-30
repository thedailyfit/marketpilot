"""
India VIX (Volatility Index) Integration
Provides VIX-based trading filters and volatility regime detection.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass
import logging

try:
    from upstox_client import MarketQuoteApi
    HAS_UPSTOX = True
except ImportError:
    HAS_UPSTOX = False

from core.config_manager import sys_config


logger = logging.getLogger(__name__)


@dataclass
class VIXData:
    """India VIX data."""
    value: float
    timestamp: datetime
    regime: str  # "LOW", "NORMAL", "HIGH", "EXTREME"
    recommendation: str


class IndiaVIXTracker:
    """
    Tracks India VIX and provides trading recommendations.
    
    VIX Levels (India specific):
    - < 12: Very Low volatility (avoid trading, no momentum)
    - 12-15: Low volatility (normal, trade cautiously)
    - 15-20: Normal volatility (ideal for trading)
    - 20-25: High volatility (widen stops, reduce position size)
    - > 25: Extreme volatility (pause trading or use hedged strategies)
    """
    
    # VIX thresholds
    VERY_LOW = 12
    LOW = 15
    NORMAL = 20
    HIGH = 25
    
    def __init__(self):
        self.current_vix: float = 15.0
        self.last_update: datetime = datetime.now()
        self.vix_history: list = []
        self.cache_ttl = 300  # 5 minutes cache
        
    async def fetch_vix(self) -> float:
        """
        Fetch current India VIX from Upstox API.
        Falls back to simulated data if unavailable.
        """
        if not HAS_UPSTOX or not sys_config.ACCESS_TOKEN:
            return self._simulate_vix()
        
        try:
            from upstox_client import Configuration, ApiClient
            
            config = Configuration()
            config.access_token = sys_config.ACCESS_TOKEN
            
            api_client = ApiClient(config)
            quote_api = MarketQuoteApi(api_client)
            
            # VIX instrument key for NSE
            vix_key = "NSE_INDEX|India VIX"
            
            # Real API call (synchronous, run in thread for async)
            import asyncio
            response = await asyncio.to_thread(
                quote_api.get_market_quote_quotes,
                instrument_key=vix_key
            )
            
            if response and response.data and vix_key in response.data:
                vix_value = response.data[vix_key].last_price
                logger.info(f"Real VIX fetched: {vix_value}")
                return vix_value
            else:
                logger.warning("VIX API returned no data, using simulation")
                return self._simulate_vix()
            
        except Exception as e:
            logger.error(f"Error fetching VIX: {e}")
            return self._simulate_vix()
    
    def _simulate_vix(self) -> float:
        """Generate simulated VIX for testing."""
        import random
        
        # VIX typically ranges from 10 to 30 in Indian markets
        # Use random walk from current value
        change = random.uniform(-0.5, 0.5)
        self.current_vix = max(10, min(35, self.current_vix + change))
        
        return round(self.current_vix, 2)
    
    def get_regime(self, vix: float) -> str:
        """Determine volatility regime from VIX value."""
        if vix < self.VERY_LOW:
            return "VERY_LOW"
        elif vix < self.LOW:
            return "LOW"
        elif vix < self.NORMAL:
            return "NORMAL"
        elif vix < self.HIGH:
            return "HIGH"
        else:
            return "EXTREME"
    
    def get_recommendation(self, vix: float) -> str:
        """Get trading recommendation based on VIX."""
        regime = self.get_regime(vix)
        
        recommendations = {
            "VERY_LOW": "SKIP - No momentum expected. Avoid option buying.",
            "LOW": "CAUTION - Low volatility. Consider option selling strategies.",
            "NORMAL": "IDEAL - Good for directional trading. Normal SL/TP.",
            "HIGH": "REDUCE SIZE - High volatility. Widen SL by 50%, reduce position size.",
            "EXTREME": "PAUSE - Extreme volatility. Only trade hedged strategies or stay out."
        }
        
        return recommendations.get(regime, "UNKNOWN")
    
    def get_stop_loss_multiplier(self, vix: float) -> float:
        """
        Get SL multiplier based on VIX.
        Higher VIX = wider stops needed.
        """
        regime = self.get_regime(vix)
        
        multipliers = {
            "VERY_LOW": 0.8,   # Tighter stops (less movement expected)
            "LOW": 1.0,        # Normal stops
            "NORMAL": 1.0,     # Normal stops
            "HIGH": 1.5,       # 50% wider stops
            "EXTREME": 2.0     # Double the stops
        }
        
        return multipliers.get(regime, 1.0)
    
    def get_position_size_multiplier(self, vix: float) -> float:
        """
        Get position size multiplier based on VIX.
        Higher VIX = smaller positions.
        """
        regime = self.get_regime(vix)
        
        multipliers = {
            "VERY_LOW": 0.5,   # Reduced (low opportunity)
            "LOW": 0.8,        # Slightly reduced
            "NORMAL": 1.0,     # Full position
            "HIGH": 0.5,       # Half position
            "EXTREME": 0.25    # Quarter position
        }
        
        return multipliers.get(regime, 1.0)
    
    def should_trade(self, vix: float) -> bool:
        """Determine if trading is advisable based on VIX."""
        regime = self.get_regime(vix)
        
        # Skip trading in very low or extreme VIX
        if regime in ["VERY_LOW", "EXTREME"]:
            return False
        
        return True
    
    async def get_vix_data(self) -> VIXData:
        """Get complete VIX analysis."""
        # Check cache
        if (datetime.now() - self.last_update).seconds < self.cache_ttl:
            vix = self.current_vix
        else:
            vix = await self.fetch_vix()
            self.current_vix = vix
            self.last_update = datetime.now()
            
            # Store in history
            self.vix_history.append({
                'timestamp': self.last_update,
                'value': vix
            })
            self.vix_history = self.vix_history[-100:]  # Keep last 100
        
        return VIXData(
            value=vix,
            timestamp=self.last_update,
            regime=self.get_regime(vix),
            recommendation=self.get_recommendation(vix)
        )
    
    def get_vix_trend(self) -> str:
        """Determine if VIX is rising or falling."""
        if len(self.vix_history) < 5:
            return "NEUTRAL"
        
        recent = [h['value'] for h in self.vix_history[-5:]]
        older = [h['value'] for h in self.vix_history[-10:-5]] if len(self.vix_history) >= 10 else recent
        
        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older)
        
        if avg_recent > avg_older * 1.05:  # 5% higher
            return "RISING"  # Fear increasing
        elif avg_recent < avg_older * 0.95:  # 5% lower
            return "FALLING"  # Fear decreasing
        else:
            return "STABLE"


# Global instance
vix_tracker = IndiaVIXTracker()

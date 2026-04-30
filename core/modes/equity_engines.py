"""
EQUITY Mode Engines
Specialized intelligence for Indian cash equity/stock trading.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import deque
from core.event_bus import bus, EventType
from core.trading_mode import is_equity_mode


# ============================================================
# SUPPORT/RESISTANCE ENGINE
# ============================================================
@dataclass
class SRLevel:
    """Support or Resistance level."""
    price: float
    level_type: str  # SUPPORT, RESISTANCE
    strength: int    # 1-5 (number of touches)
    last_touch: int
    volume_at_level: float = 0.0


class SupportResistanceEngine:
    """
    Detects key Support and Resistance levels for stocks.
    
    Methods:
    - Swing high/low detection
    - Volume profile clustering
    - Round number identification
    - Historical pivot levels
    """
    def __init__(self):
        self.logger = logging.getLogger("SupportResistanceEngine")
        self.levels: Dict[str, List[SRLevel]] = {}  # symbol -> [levels]
        self.price_history: Dict[str, deque] = {}   # symbol -> recent prices
        self.is_running = False
        self.window_size = 20  # Lookback for swing detection
        
    async def on_start(self):
        self.logger.info("📊 Starting Support/Resistance Engine...")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._on_tick)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Support/Resistance Engine Stopped")
        
    async def _on_tick(self, tick_data: dict):
        if not self.is_running or not is_equity_mode():
            return
            
        symbol = tick_data.get('symbol', '')
        price = float(tick_data.get('ltp', 0))
        
        if not symbol or price <= 0:
            return
            
        # Initialize if needed
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=100)
            self.levels[symbol] = []
        
        self.price_history[symbol].append(price)
        
        # Recalculate levels periodically
        if len(self.price_history[symbol]) >= self.window_size:
            await self._calculate_levels(symbol)
    
    async def _calculate_levels(self, symbol: str):
        """Calculate S/R levels from price history."""
        prices = list(self.price_history[symbol])
        if len(prices) < self.window_size:
            return
        
        levels = []
        
        # 1. Swing Highs (Resistance)
        for i in range(2, len(prices) - 2):
            if prices[i] > prices[i-1] and prices[i] > prices[i-2] and \
               prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                levels.append(SRLevel(
                    price=prices[i],
                    level_type="RESISTANCE",
                    strength=1,
                    last_touch=int(datetime.now().timestamp())
                ))
        
        # 2. Swing Lows (Support)
        for i in range(2, len(prices) - 2):
            if prices[i] < prices[i-1] and prices[i] < prices[i-2] and \
               prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                levels.append(SRLevel(
                    price=prices[i],
                    level_type="SUPPORT",
                    strength=1,
                    last_touch=int(datetime.now().timestamp())
                ))
        
        # 3. Round Numbers
        current = prices[-1]
        round_interval = self._get_round_interval(current)
        round_levels = []
        for i in range(-3, 4):
            round_price = round(current / round_interval) * round_interval + (i * round_interval)
            if round_price > 0:
                round_levels.append(SRLevel(
                    price=round_price,
                    level_type="SUPPORT" if round_price < current else "RESISTANCE",
                    strength=2,
                    last_touch=int(datetime.now().timestamp())
                ))
        
        levels.extend(round_levels)
        
        # Cluster similar levels
        self.levels[symbol] = self._cluster_levels(levels)
    
    def _get_round_interval(self, price: float) -> float:
        """Get appropriate round number interval based on price."""
        if price > 10000:
            return 100
        elif price > 1000:
            return 50
        elif price > 100:
            return 10
        else:
            return 5
    
    def _cluster_levels(self, levels: List[SRLevel], threshold: float = 0.002) -> List[SRLevel]:
        """Cluster nearby levels and increase strength."""
        if not levels:
            return []
        
        sorted_levels = sorted(levels, key=lambda x: x.price)
        clustered = []
        
        current_cluster = [sorted_levels[0]]
        for level in sorted_levels[1:]:
            if abs(level.price - current_cluster[-1].price) / current_cluster[-1].price < threshold:
                current_cluster.append(level)
            else:
                # Merge cluster
                avg_price = sum(l.price for l in current_cluster) / len(current_cluster)
                strength = min(5, len(current_cluster))
                level_type = max(set(l.level_type for l in current_cluster), 
                                key=lambda x: sum(1 for l in current_cluster if l.level_type == x))
                clustered.append(SRLevel(
                    price=avg_price,
                    level_type=level_type,
                    strength=strength,
                    last_touch=max(l.last_touch for l in current_cluster)
                ))
                current_cluster = [level]
        
        # Don't forget last cluster
        if current_cluster:
            avg_price = sum(l.price for l in current_cluster) / len(current_cluster)
            strength = min(5, len(current_cluster))
            clustered.append(SRLevel(
                price=avg_price,
                level_type=current_cluster[0].level_type,
                strength=strength,
                last_touch=max(l.last_touch for l in current_cluster)
            ))
        
        return clustered
    
    def get_levels(self, symbol: str) -> List[dict]:
        """Get S/R levels for a symbol."""
        return [
            {
                "price": l.price,
                "type": l.level_type,
                "strength": l.strength
            }
            for l in self.levels.get(symbol, [])
        ]
    
    def get_nearest(self, symbol: str, current_price: float) -> dict:
        """Get nearest support and resistance."""
        levels = self.levels.get(symbol, [])
        
        supports = [l for l in levels if l.price < current_price]
        resistances = [l for l in levels if l.price > current_price]
        
        nearest_support = max(supports, key=lambda x: x.price) if supports else None
        nearest_resistance = min(resistances, key=lambda x: x.price) if resistances else None
        
        return {
            "support": nearest_support.price if nearest_support else None,
            "resistance": nearest_resistance.price if nearest_resistance else None,
            "support_strength": nearest_support.strength if nearest_support else 0,
            "resistance_strength": nearest_resistance.strength if nearest_resistance else 0
        }


# ============================================================
# TREND ENGINE
# ============================================================
@dataclass
class TrendState:
    """Current trend state."""
    symbol: str
    direction: str  # UPTREND, DOWNTREND, SIDEWAYS
    strength: float  # 0-100
    ema_fast: float
    ema_slow: float
    higher_highs: int
    lower_lows: int
    timestamp: int


class TrendEngine:
    """
    Detects trend direction and strength for stocks.
    
    Methods:
    - EMA crossover (9/21)
    - Higher highs / Lower lows
    - ADX-like strength measurement
    """
    def __init__(self):
        self.logger = logging.getLogger("TrendEngine")
        self.trends: Dict[str, TrendState] = {}
        self.price_data: Dict[str, deque] = {}
        self.ema_fast: Dict[str, float] = {}  # 9 period
        self.ema_slow: Dict[str, float] = {}  # 21 period
        self.is_running = False
        
    async def on_start(self):
        self.logger.info("📈 Starting Trend Engine...")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._on_tick)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Trend Engine Stopped")
        
    async def _on_tick(self, tick_data: dict):
        if not self.is_running or not is_equity_mode():
            return
            
        symbol = tick_data.get('symbol', '')
        price = float(tick_data.get('ltp', 0))
        
        if not symbol or price <= 0:
            return
        
        # Update EMAs
        if symbol not in self.ema_fast:
            self.ema_fast[symbol] = price
            self.ema_slow[symbol] = price
            self.price_data[symbol] = deque(maxlen=50)
        
        # EMA calculation
        k_fast = 2 / (9 + 1)
        k_slow = 2 / (21 + 1)
        self.ema_fast[symbol] = price * k_fast + self.ema_fast[symbol] * (1 - k_fast)
        self.ema_slow[symbol] = price * k_slow + self.ema_slow[symbol] * (1 - k_slow)
        
        self.price_data[symbol].append(price)
        
        # Determine trend
        await self._calculate_trend(symbol, price)
    
    async def _calculate_trend(self, symbol: str, current_price: float):
        """Calculate trend direction and strength."""
        ema_f = self.ema_fast[symbol]
        ema_s = self.ema_slow[symbol]
        
        # Direction
        if ema_f > ema_s * 1.002:  # 0.2% buffer
            direction = "UPTREND"
        elif ema_f < ema_s * 0.998:
            direction = "DOWNTREND"
        else:
            direction = "SIDEWAYS"
        
        # Strength (based on EMA gap)
        gap = abs(ema_f - ema_s) / ema_s * 100
        strength = min(100, gap * 20)  # Scale to 0-100
        
        # Count higher highs / lower lows
        prices = list(self.price_data[symbol])
        hh, ll = 0, 0
        if len(prices) >= 10:
            for i in range(5, len(prices)):
                if prices[i] > max(prices[i-5:i]):
                    hh += 1
                if prices[i] < min(prices[i-5:i]):
                    ll += 1
        
        self.trends[symbol] = TrendState(
            symbol=symbol,
            direction=direction,
            strength=strength,
            ema_fast=ema_f,
            ema_slow=ema_s,
            higher_highs=hh,
            lower_lows=ll,
            timestamp=int(datetime.now().timestamp())
        )
    
    def get_trend(self, symbol: str) -> Optional[dict]:
        """Get trend state for a symbol."""
        t = self.trends.get(symbol)
        if not t:
            return None
        return {
            "direction": t.direction,
            "strength": round(t.strength, 1),
            "ema_fast": round(t.ema_fast, 2),
            "ema_slow": round(t.ema_slow, 2),
            "higher_highs": t.higher_highs,
            "lower_lows": t.lower_lows
        }


# ============================================================
# BREAKOUT ENGINE
# ============================================================
@dataclass 
class BreakoutAlert:
    """Breakout detection alert."""
    symbol: str
    breakout_type: str  # RESISTANCE_BREAK, SUPPORT_BREAK
    level: float
    current_price: float
    volume_surge: float  # Multiplier vs average
    timestamp: int


class BreakoutEngine:
    """
    Detects breakouts from consolidation ranges.
    
    Signals:
    - Break above resistance with volume
    - Break below support with volume
    - Range expansion after compression
    """
    def __init__(self):
        self.logger = logging.getLogger("BreakoutEngine")
        self.ranges: Dict[str, Tuple[float, float]] = {}  # symbol -> (low, high)
        self.volume_avg: Dict[str, float] = {}
        self.breakouts: List[BreakoutAlert] = []
        self.is_running = False
        
    async def on_start(self):
        self.logger.info("🚀 Starting Breakout Engine...")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._on_tick)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Breakout Engine Stopped")
        
    async def _on_tick(self, tick_data: dict):
        if not self.is_running or not is_equity_mode():
            return
            
        symbol = tick_data.get('symbol', '')
        price = float(tick_data.get('ltp', 0))
        volume = float(tick_data.get('volume', 0))
        
        if not symbol or price <= 0:
            return
        
        # Initialize range
        if symbol not in self.ranges:
            self.ranges[symbol] = (price * 0.99, price * 1.01)  # 1% initial range
            self.volume_avg[symbol] = volume if volume > 0 else 10000
            return
        
        low, high = self.ranges[symbol]
        
        # Update volume average (EMA)
        if volume > 0:
            self.volume_avg[symbol] = 0.9 * self.volume_avg[symbol] + 0.1 * volume
        
        volume_surge = volume / self.volume_avg[symbol] if self.volume_avg[symbol] > 0 else 1
        
        # Check breakouts
        if price > high and volume_surge > 1.5:
            alert = BreakoutAlert(
                symbol=symbol,
                breakout_type="RESISTANCE_BREAK",
                level=high,
                current_price=price,
                volume_surge=volume_surge,
                timestamp=int(datetime.now().timestamp())
            )
            self.breakouts.append(alert)
            self.logger.info(f"🚀 BREAKOUT UP: {symbol} broke {high:.2f} (Vol: {volume_surge:.1f}x)")
            # Update range
            self.ranges[symbol] = (low, price)
            
        elif price < low and volume_surge > 1.5:
            alert = BreakoutAlert(
                symbol=symbol,
                breakout_type="SUPPORT_BREAK",
                level=low,
                current_price=price,
                volume_surge=volume_surge,
                timestamp=int(datetime.now().timestamp())
            )
            self.breakouts.append(alert)
            self.logger.info(f"📉 BREAKDOWN: {symbol} broke {low:.2f} (Vol: {volume_surge:.1f}x)")
            # Update range
            self.ranges[symbol] = (price, high)
        else:
            # Narrow the range over time (consolidation detection)
            new_low = max(low, price * 0.995)
            new_high = min(high, price * 1.005)
            if new_high > new_low:
                self.ranges[symbol] = (new_low, new_high)
    
    def get_recent_breakouts(self, limit: int = 5) -> List[dict]:
        """Get recent breakout alerts."""
        recent = sorted(self.breakouts, key=lambda x: x.timestamp, reverse=True)[:limit]
        return [
            {
                "symbol": b.symbol,
                "type": b.breakout_type,
                "level": b.level,
                "price": b.current_price,
                "volume_surge": round(b.volume_surge, 1),
                "time": b.timestamp
            }
            for b in recent
        ]


# ============================================================
# MOMENTUM ENGINE
# ============================================================
class MomentumEngine:
    """
    Tracks momentum indicators for stocks.
    
    Indicators:
    - RSI (14 period)
    - Rate of Change
    - Momentum oscillator
    """
    def __init__(self):
        self.logger = logging.getLogger("MomentumEngine")
        self.rsi: Dict[str, float] = {}
        self.roc: Dict[str, float] = {}
        self.price_history: Dict[str, deque] = {}
        self.gains: Dict[str, deque] = {}
        self.losses: Dict[str, deque] = {}
        self.is_running = False
        
    async def on_start(self):
        self.logger.info("⚡ Starting Momentum Engine...")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._on_tick)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Momentum Engine Stopped")
        
    async def _on_tick(self, tick_data: dict):
        if not self.is_running or not is_equity_mode():
            return
            
        symbol = tick_data.get('symbol', '')
        price = float(tick_data.get('ltp', 0))
        
        if not symbol or price <= 0:
            return
        
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=20)
            self.gains[symbol] = deque(maxlen=14)
            self.losses[symbol] = deque(maxlen=14)
            self.rsi[symbol] = 50
            self.roc[symbol] = 0
        
        # Calculate change
        if len(self.price_history[symbol]) > 0:
            prev_price = self.price_history[symbol][-1]
            change = price - prev_price
            
            if change > 0:
                self.gains[symbol].append(change)
                self.losses[symbol].append(0)
            else:
                self.gains[symbol].append(0)
                self.losses[symbol].append(abs(change))
            
            # RSI calculation
            if len(self.gains[symbol]) >= 14:
                avg_gain = sum(self.gains[symbol]) / 14
                avg_loss = sum(self.losses[symbol]) / 14
                
                if avg_loss > 0:
                    rs = avg_gain / avg_loss
                    self.rsi[symbol] = 100 - (100 / (1 + rs))
                else:
                    self.rsi[symbol] = 100
            
            # Rate of Change (10 period)
            if len(self.price_history[symbol]) >= 10:
                old_price = self.price_history[symbol][-10]
                self.roc[symbol] = ((price - old_price) / old_price) * 100
        
        self.price_history[symbol].append(price)
    
    def get_momentum(self, symbol: str) -> dict:
        """Get momentum indicators for a symbol."""
        rsi = self.rsi.get(symbol, 50)
        roc = self.roc.get(symbol, 0)
        
        # Momentum signal
        if rsi > 70:
            signal = "OVERBOUGHT"
        elif rsi < 30:
            signal = "OVERSOLD"
        elif roc > 2:
            signal = "BULLISH_MOMENTUM"
        elif roc < -2:
            signal = "BEARISH_MOMENTUM"
        else:
            signal = "NEUTRAL"
        
        return {
            "rsi": round(rsi, 1),
            "roc": round(roc, 2),
            "signal": signal
        }


# ============================================================
# SINGLETON INSTANCES
# ============================================================
support_resistance_engine = SupportResistanceEngine()
trend_engine = TrendEngine()
breakout_engine = BreakoutEngine()
momentum_engine = MomentumEngine()

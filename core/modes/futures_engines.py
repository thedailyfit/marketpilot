"""
FUTURES Mode Engines
Specialized intelligence for Indian index/stock futures trading.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
from core.event_bus import bus, EventType
from core.trading_mode import is_futures_mode


# ============================================================
# BASIS ENGINE
# ============================================================
@dataclass
class BasisState:
    """Spot-Futures basis state."""
    symbol: str
    spot_price: float
    futures_price: float
    basis: float           # Absolute difference
    basis_percent: float   # Percentage difference
    days_to_expiry: int
    annualized_basis: float
    signal: str            # PREMIUM, DISCOUNT, FAIR
    timestamp: int


class BasisEngine:
    """
    Tracks Spot-Futures basis for F&O instruments.
    
    Key Metrics:
    - Absolute basis (Futures - Spot)
    - Percentage basis
    - Annualized basis (cost of carry)
    - Premium/Discount detection
    """
    def __init__(self):
        self.logger = logging.getLogger("BasisEngine")
        self.spot_prices: Dict[str, float] = {}
        self.futures_prices: Dict[str, float] = {}
        self.basis_states: Dict[str, BasisState] = {}
        self.is_running = False
        
        # Expiry dates (monthly - last Thursday)
        self.current_expiry = self._get_current_expiry()
        
    def _get_current_expiry(self) -> datetime:
        """Get current month's expiry (last Thursday)."""
        today = datetime.now()
        # Find last Thursday of current month
        next_month = today.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        
        # Find last Thursday
        days_to_thursday = (last_day.weekday() - 3) % 7
        last_thursday = last_day - timedelta(days=days_to_thursday)
        
        return last_thursday
        
    async def on_start(self):
        self.logger.info("📊 Starting Basis Engine...")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._on_tick)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Basis Engine Stopped")
        
    async def _on_tick(self, tick_data: dict):
        if not self.is_running or not is_futures_mode():
            return
            
        symbol = tick_data.get('symbol', '')
        price = float(tick_data.get('ltp', 0))
        
        if not symbol or price <= 0:
            return
        
        # Identify if spot or futures
        base_symbol = self._get_base_symbol(symbol)
        
        if 'FUT' in symbol.upper() or any(month in symbol.upper() for month in ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']):
            self.futures_prices[base_symbol] = price
        else:
            self.spot_prices[base_symbol] = price
        
        # Calculate basis if we have both prices
        if base_symbol in self.spot_prices and base_symbol in self.futures_prices:
            await self._calculate_basis(base_symbol)
    
    def _get_base_symbol(self, symbol: str) -> str:
        """Extract base symbol from futures symbol."""
        # Remove FUT suffix and month codes
        base = symbol.upper()
        for suffix in ['FUT', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']:
            base = base.replace(suffix, '')
        return base.strip()
    
    async def _calculate_basis(self, symbol: str):
        """Calculate spot-futures basis."""
        spot = self.spot_prices[symbol]
        futures = self.futures_prices[symbol]
        
        if spot <= 0:
            return
        
        basis = futures - spot
        basis_percent = (basis / spot) * 100
        
        # Days to expiry
        today = datetime.now()
        days_to_expiry = max(1, (self.current_expiry - today).days)
        
        # Annualized basis
        annualized = (basis_percent / days_to_expiry) * 365
        
        # Signal
        if basis_percent > 0.5:
            signal = "PREMIUM"
        elif basis_percent < -0.5:
            signal = "DISCOUNT"
        else:
            signal = "FAIR"
        
        self.basis_states[symbol] = BasisState(
            symbol=symbol,
            spot_price=spot,
            futures_price=futures,
            basis=basis,
            basis_percent=basis_percent,
            days_to_expiry=days_to_expiry,
            annualized_basis=annualized,
            signal=signal,
            timestamp=int(datetime.now().timestamp())
        )
        
        if abs(basis_percent) > 1.0:
            self.logger.info(f"📊 BASIS ALERT: {symbol} {signal} {basis_percent:.2f}%")
    
    def get_basis(self, symbol: str) -> Optional[dict]:
        """Get basis state for a symbol."""
        state = self.basis_states.get(symbol)
        if not state:
            return None
        return {
            "spot": state.spot_price,
            "futures": state.futures_price,
            "basis": round(state.basis, 2),
            "basis_pct": round(state.basis_percent, 3),
            "days_to_expiry": state.days_to_expiry,
            "annualized": round(state.annualized_basis, 2),
            "signal": state.signal
        }


# ============================================================
# ROLLOVER ENGINE
# ============================================================
@dataclass
class RolloverState:
    """Rollover tracking state."""
    symbol: str
    near_month_oi: int
    far_month_oi: int
    rollover_percent: float
    rollover_direction: str  # ROLLING, HOLDING, UNWINDING
    days_to_expiry: int
    timestamp: int


class RolloverEngine:
    """
    Tracks futures rollover activity near expiry.
    
    Key Metrics:
    - Near vs Far month OI
    - Rollover percentage
    - Position unwinding detection
    """
    def __init__(self):
        self.logger = logging.getLogger("RolloverEngine")
        self.oi_data: Dict[str, Dict[str, int]] = {}  # symbol -> {near: oi, far: oi}
        self.rollover_states: Dict[str, RolloverState] = {}
        self.is_running = False
        
    async def on_start(self):
        self.logger.info("🔄 Starting Rollover Engine...")
        self.is_running = True
        # Would subscribe to OI data events
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Rollover Engine Stopped")
    
    def update_oi(self, symbol: str, near_oi: int, far_oi: int, days_to_expiry: int):
        """Update OI data for rollover calculation."""
        if not is_futures_mode():
            return
            
        total_oi = near_oi + far_oi
        if total_oi == 0:
            return
        
        rollover_pct = (far_oi / total_oi) * 100
        
        # Determine rollover direction
        prev_state = self.rollover_states.get(symbol)
        if prev_state:
            if rollover_pct > prev_state.rollover_percent + 1:
                direction = "ROLLING"
            elif rollover_pct < prev_state.rollover_percent - 1:
                direction = "UNWINDING"
            else:
                direction = "HOLDING"
        else:
            direction = "HOLDING"
        
        self.rollover_states[symbol] = RolloverState(
            symbol=symbol,
            near_month_oi=near_oi,
            far_month_oi=far_oi,
            rollover_percent=rollover_pct,
            rollover_direction=direction,
            days_to_expiry=days_to_expiry,
            timestamp=int(datetime.now().timestamp())
        )
        
        if days_to_expiry <= 5 and rollover_pct < 50:
            self.logger.warning(f"⚠️ LOW ROLLOVER: {symbol} only {rollover_pct:.1f}% rolled with {days_to_expiry} days left")
    
    def get_rollover(self, symbol: str) -> Optional[dict]:
        """Get rollover state."""
        state = self.rollover_states.get(symbol)
        if not state:
            return None
        return {
            "near_oi": state.near_month_oi,
            "far_oi": state.far_month_oi,
            "rollover_pct": round(state.rollover_percent, 1),
            "direction": state.rollover_direction,
            "days_to_expiry": state.days_to_expiry
        }


# ============================================================
# CONTANGO ENGINE
# ============================================================
@dataclass
class ContangoState:
    """Contango/Backwardation state."""
    symbol: str
    near_price: float
    far_price: float
    spread: float
    spread_percent: float
    market_type: str  # CONTANGO, BACKWARDATION, FLAT
    timestamp: int


class ContangoEngine:
    """
    Detects Contango (futures > spot) vs Backwardation (futures < spot).
    
    Use Cases:
    - Calendar spread opportunities
    - Market sentiment indicator
    - Cost of carry analysis
    """
    def __init__(self):
        self.logger = logging.getLogger("ContangoEngine")
        self.states: Dict[str, ContangoState] = {}
        self.near_prices: Dict[str, float] = {}
        self.far_prices: Dict[str, float] = {}
        self.is_running = False
        
    async def on_start(self):
        self.logger.info("📈 Starting Contango Engine...")
        self.is_running = True
        bus.subscribe(EventType.TICK, self._on_tick)
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Contango Engine Stopped")
        
    async def _on_tick(self, tick_data: dict):
        if not self.is_running or not is_futures_mode():
            return
            
        symbol = tick_data.get('symbol', '')
        price = float(tick_data.get('ltp', 0))
        
        if not symbol or price <= 0:
            return
        
        # Identify near vs far month (simplified)
        base = self._get_base_symbol(symbol)
        
        if 'NEAR' in symbol.upper() or 'I' in symbol[-1:]:
            self.near_prices[base] = price
        elif 'FAR' in symbol.upper() or 'II' in symbol[-2:]:
            self.far_prices[base] = price
        
        # Calculate if we have both
        if base in self.near_prices and base in self.far_prices:
            await self._calculate_contango(base)
    
    def _get_base_symbol(self, symbol: str) -> str:
        """Extract base symbol."""
        return symbol.replace('FUT', '').replace('NEAR', '').replace('FAR', '').strip()
    
    async def _calculate_contango(self, symbol: str):
        """Calculate contango/backwardation."""
        near = self.near_prices[symbol]
        far = self.far_prices[symbol]
        
        if near <= 0:
            return
        
        spread = far - near
        spread_pct = (spread / near) * 100
        
        if spread_pct > 0.2:
            market_type = "CONTANGO"
        elif spread_pct < -0.2:
            market_type = "BACKWARDATION"
        else:
            market_type = "FLAT"
        
        self.states[symbol] = ContangoState(
            symbol=symbol,
            near_price=near,
            far_price=far,
            spread=spread,
            spread_percent=spread_pct,
            market_type=market_type,
            timestamp=int(datetime.now().timestamp())
        )
    
    def get_contango(self, symbol: str) -> Optional[dict]:
        """Get contango state."""
        state = self.states.get(symbol)
        if not state:
            return None
        return {
            "near": state.near_price,
            "far": state.far_price,
            "spread": round(state.spread, 2),
            "spread_pct": round(state.spread_percent, 3),
            "type": state.market_type
        }


# ============================================================
# SPREAD ENGINE
# ============================================================
@dataclass
class SpreadOpportunity:
    """Calendar spread opportunity."""
    symbol: str
    spread_type: str  # BULL_SPREAD, BEAR_SPREAD
    near_price: float
    far_price: float
    spread_value: float
    z_score: float  # How many std devs from mean
    timestamp: int


class SpreadEngine:
    """
    Identifies calendar spread opportunities in futures.
    
    Strategies:
    - Bull Calendar (buy near, sell far in contango)
    - Bear Calendar (sell near, buy far in backwardation)
    - Mean reversion spreads
    """
    def __init__(self):
        self.logger = logging.getLogger("SpreadEngine")
        self.spread_history: Dict[str, deque] = {}  # For calculating mean/std
        self.opportunities: List[SpreadOpportunity] = []
        self.is_running = False
        
    async def on_start(self):
        self.logger.info("📊 Starting Spread Engine...")
        self.is_running = True
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Spread Engine Stopped")
    
    def analyze_spread(self, symbol: str, near_price: float, far_price: float):
        """Analyze spread for opportunities."""
        if not is_futures_mode():
            return
            
        spread = far_price - near_price
        
        # Initialize history
        if symbol not in self.spread_history:
            self.spread_history[symbol] = deque(maxlen=100)
        
        self.spread_history[symbol].append(spread)
        
        # Need enough history
        if len(self.spread_history[symbol]) < 20:
            return
        
        # Calculate z-score
        spreads = list(self.spread_history[symbol])
        mean = sum(spreads) / len(spreads)
        variance = sum((x - mean) ** 2 for x in spreads) / len(spreads)
        std = variance ** 0.5 if variance > 0 else 1
        
        z_score = (spread - mean) / std if std > 0 else 0
        
        # Identify opportunities
        if z_score > 2:
            # Spread unusually wide - expect contraction
            opp = SpreadOpportunity(
                symbol=symbol,
                spread_type="BEAR_SPREAD",
                near_price=near_price,
                far_price=far_price,
                spread_value=spread,
                z_score=z_score,
                timestamp=int(datetime.now().timestamp())
            )
            self.opportunities.append(opp)
            self.logger.info(f"📊 SPREAD OPP: {symbol} BEAR (z={z_score:.1f})")
            
        elif z_score < -2:
            # Spread unusually narrow - expect expansion
            opp = SpreadOpportunity(
                symbol=symbol,
                spread_type="BULL_SPREAD",
                near_price=near_price,
                far_price=far_price,
                spread_value=spread,
                z_score=z_score,
                timestamp=int(datetime.now().timestamp())
            )
            self.opportunities.append(opp)
            self.logger.info(f"📊 SPREAD OPP: {symbol} BULL (z={z_score:.1f})")
    
    def get_opportunities(self, limit: int = 5) -> List[dict]:
        """Get recent spread opportunities."""
        recent = sorted(self.opportunities, key=lambda x: abs(x.z_score), reverse=True)[:limit]
        return [
            {
                "symbol": o.symbol,
                "type": o.spread_type,
                "spread": round(o.spread_value, 2),
                "z_score": round(o.z_score, 1),
                "time": o.timestamp
            }
            for o in recent
        ]


# ============================================================
# SINGLETON INSTANCES
# ============================================================
basis_engine = BasisEngine()
rollover_engine = RolloverEngine()
contango_engine = ContangoEngine()
spread_engine = SpreadEngine()

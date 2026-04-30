"""
IV Surface Engine
Builds and analyzes implied volatility surfaces for options.
"""
import logging
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from collections import deque
import numpy as np
from .chain_snapshot import OptionSnapshot


@dataclass
class IVSurface:
    """Implied Volatility Surface snapshot."""
    symbol: str
    timestamp: int
    spot_price: float
    
    # ATM IV
    atm_iv: float
    
    # Skew: strike_offset (as % of spot) -> IV
    # e.g., {-5: 0.18, -2: 0.16, 0: 0.15, 2: 0.14, 5: 0.13}
    skew: Dict[int, float] = field(default_factory=dict)
    
    # Term structure: expiry -> ATM IV
    term_structure: Dict[str, float] = field(default_factory=dict)
    
    # Percentile vs last 30 days
    iv_percentile: float = 50.0
    
    # IV Regime
    regime: str = "NORMAL"  # HIGH_IV, LOW_IV, CRUSH_RISK, EXPANSION_LIKELY
    
    # Additional metrics
    put_call_skew: float = 0.0  # PE IV - CE IV at ATM
    wings_premium: float = 0.0  # OTM IV premium over ATM
    
    def to_dict(self) -> dict:
        return asdict(self)


class IVSurfaceEngine:
    """
    Builds and stores IV surface for analysis.
    
    Features:
    - IV surface construction from option chain
    - Skew analysis (OTM put vs OTM call IV)
    - Term structure (near vs far expiry IV)
    - IV percentile ranking vs history
    - IV regime detection (crush/expansion risk)
    
    Storage: data/options/iv_surface/{symbol}/{date}.json
    """
    
    def __init__(self):
        self.logger = logging.getLogger("IVSurfaceEngine")
        self.data_path = Path("data/options/iv_surface")
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Historical IV for percentile calculation
        self.iv_history: Dict[str, deque] = {}  # symbol -> [atm_iv, ...]
        self.history_days = 30
        
        # Current surface
        self.current_surface: Dict[str, IVSurface] = {}
        
        self.is_running = False
    
    async def on_start(self):
        """Start IV surface engine."""
        self.logger.info("📊 Starting IV Surface Engine...")
        self.is_running = True
        self._load_history()
    
    async def on_stop(self):
        self.is_running = False
        self.logger.info("IV Surface Engine Stopped")
    
    def _load_history(self):
        """Load IV history from disk."""
        for symbol_dir in self.data_path.iterdir():
            if symbol_dir.is_dir():
                symbol = symbol_dir.name
                self.iv_history[symbol] = deque(maxlen=self.history_days)
                
                # Load last N days
                files = sorted(symbol_dir.glob("*.json"))[-self.history_days:]
                for f in files:
                    try:
                        with open(f) as fp:
                            data = json.load(fp)
                            self.iv_history[symbol].append(data.get('atm_iv', 0))
                    except:
                        pass
    
    def build_surface(
        self,
        symbol: str,
        spot_price: float,
        chain: List[OptionSnapshot]
    ) -> IVSurface:
        """
        Build IV surface from option chain snapshot.
        
        Args:
            symbol: Underlying symbol
            spot_price: Current spot price
            chain: List of option snapshots
        
        Returns:
            IVSurface object
        """
        if not chain:
            return IVSurface(
                symbol=symbol,
                timestamp=int(datetime.now().timestamp()),
                spot_price=spot_price,
                atm_iv=0.15,
                regime="UNKNOWN"
            )
        
        # Group by expiry
        by_expiry: Dict[str, List[OptionSnapshot]] = {}
        for opt in chain:
            if opt.expiry not in by_expiry:
                by_expiry[opt.expiry] = []
            by_expiry[opt.expiry].append(opt)
        
        # Get nearest expiry for main analysis
        expiries = sorted(by_expiry.keys())
        near_expiry = expiries[0] if expiries else None
        
        if not near_expiry:
            return IVSurface(
                symbol=symbol,
                timestamp=int(datetime.now().timestamp()),
                spot_price=spot_price,
                atm_iv=0.15,
                regime="UNKNOWN"
            )
        
        near_chain = by_expiry[near_expiry]
        
        # Find ATM strike
        strikes = set(opt.strike for opt in near_chain)
        atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
        
        # Get ATM IV
        atm_ce = next((o for o in near_chain if o.strike == atm_strike and o.option_type == 'CE'), None)
        atm_pe = next((o for o in near_chain if o.strike == atm_strike and o.option_type == 'PE'), None)
        
        if atm_ce and atm_pe:
            atm_iv = (atm_ce.iv + atm_pe.iv) / 2
        elif atm_ce:
            atm_iv = atm_ce.iv
        elif atm_pe:
            atm_iv = atm_pe.iv
        else:
            atm_iv = 0.15
        
        # Build skew
        skew = self._build_skew(near_chain, spot_price, atm_strike)
        
        # Build term structure
        term_structure = self._build_term_structure(by_expiry, spot_price)
        
        # Calculate put-call skew
        put_call_skew = 0.0
        if atm_ce and atm_pe:
            put_call_skew = atm_pe.iv - atm_ce.iv
        
        # Calculate wings premium
        wings_premium = self._calculate_wings_premium(near_chain, atm_iv, spot_price)
        
        # Calculate percentile
        iv_percentile = self._calculate_percentile(symbol, atm_iv)
        
        # Detect regime
        regime = self._detect_regime(atm_iv, iv_percentile, put_call_skew, wings_premium)
        
        surface = IVSurface(
            symbol=symbol,
            timestamp=int(datetime.now().timestamp()),
            spot_price=spot_price,
            atm_iv=round(atm_iv, 4),
            skew=skew,
            term_structure=term_structure,
            iv_percentile=round(iv_percentile, 1),
            regime=regime,
            put_call_skew=round(put_call_skew, 4),
            wings_premium=round(wings_premium, 4)
        )
        
        # Cache and persist
        self.current_surface[symbol] = surface
        self._update_history(symbol, atm_iv)
        self._persist_surface(symbol, surface)
        
        self.logger.info(f"📊 IV Surface: {symbol} ATM={atm_iv*100:.1f}% Regime={regime}")
        
        return surface
    
    def _build_skew(
        self,
        chain: List[OptionSnapshot],
        spot: float,
        atm_strike: float
    ) -> Dict[int, float]:
        """Build IV skew by strike offset."""
        skew = {}
        
        for opt in chain:
            # Calculate % offset from spot
            offset_pct = int(round((opt.strike - spot) / spot * 100))
            
            # Only keep reasonable offsets
            if abs(offset_pct) <= 10:
                if offset_pct not in skew:
                    skew[offset_pct] = opt.iv
                else:
                    # Average CE and PE IV at same strike
                    skew[offset_pct] = (skew[offset_pct] + opt.iv) / 2
        
        return {k: round(v, 4) for k, v in sorted(skew.items())}
    
    def _build_term_structure(
        self,
        by_expiry: Dict[str, List[OptionSnapshot]],
        spot: float
    ) -> Dict[str, float]:
        """Build IV term structure by expiry."""
        term_structure = {}
        
        for expiry, chain in by_expiry.items():
            # Find ATM strike for this expiry
            strikes = set(opt.strike for opt in chain)
            if not strikes:
                continue
            
            atm_strike = min(strikes, key=lambda x: abs(x - spot))
            
            # Get ATM options
            atm_opts = [o for o in chain if o.strike == atm_strike]
            
            if atm_opts:
                avg_iv = sum(o.iv for o in atm_opts) / len(atm_opts)
                term_structure[expiry] = round(avg_iv, 4)
        
        return term_structure
    
    def _calculate_wings_premium(
        self,
        chain: List[OptionSnapshot],
        atm_iv: float,
        spot: float
    ) -> float:
        """Calculate OTM wings premium over ATM IV."""
        wing_ivs = []
        
        for opt in chain:
            offset_pct = abs((opt.strike - spot) / spot * 100)
            # Wings are 3-5% OTM
            if 3 <= offset_pct <= 5:
                wing_ivs.append(opt.iv)
        
        if not wing_ivs or atm_iv <= 0:
            return 0.0
        
        avg_wing_iv = sum(wing_ivs) / len(wing_ivs)
        return (avg_wing_iv - atm_iv) / atm_iv
    
    def _calculate_percentile(self, symbol: str, current_iv: float) -> float:
        """Calculate IV percentile vs last 30 days."""
        history = self.iv_history.get(symbol, deque())
        
        if len(history) < 5:
            return 50.0  # Default if not enough history
        
        lower_count = sum(1 for iv in history if iv < current_iv)
        return (lower_count / len(history)) * 100
    
    def _detect_regime(
        self,
        atm_iv: float,
        percentile: float,
        put_call_skew: float,
        wings_premium: float
    ) -> str:
        """
        Detect IV regime.
        
        Regimes:
        - HIGH_IV: Percentile > 80, good for selling
        - LOW_IV: Percentile < 20, good for buying
        - CRUSH_RISK: High IV + event expected, crush likely
        - EXPANSION_LIKELY: Low IV + unusual activity
        - NORMAL: Everything else
        """
        # High IV regime
        if percentile > 80:
            # Check for crush risk (high IV + high wings = potential event)
            if wings_premium > 0.15:
                return "CRUSH_RISK"
            return "HIGH_IV"
        
        # Low IV regime
        if percentile < 20:
            # Check for expansion (low IV + high put skew = fear building)
            if put_call_skew > 0.02:
                return "EXPANSION_LIKELY"
            return "LOW_IV"
        
        # Moderate levels
        if percentile > 60 and put_call_skew > 0.03:
            return "CRUSH_RISK"
        
        if percentile < 40 and wings_premium > 0.10:
            return "EXPANSION_LIKELY"
        
        return "NORMAL"
    
    def _update_history(self, symbol: str, iv: float):
        """Add IV to history."""
        if symbol not in self.iv_history:
            self.iv_history[symbol] = deque(maxlen=self.history_days)
        self.iv_history[symbol].append(iv)
    
    def _persist_surface(self, symbol: str, surface: IVSurface):
        """Save surface to disk."""
        symbol_path = self.data_path / symbol
        symbol_path.mkdir(exist_ok=True)
        
        today = date.today().isoformat()
        file_path = symbol_path / f"{today}.json"
        
        with open(file_path, 'w') as f:
            json.dump(surface.to_dict(), f, indent=2)
    
    def get_surface(self, symbol: str) -> Optional[IVSurface]:
        """Get current IV surface for symbol."""
        return self.current_surface.get(symbol)
    
    def get_iv_at_strike(
        self,
        symbol: str,
        strike: float,
        spot: float
    ) -> Optional[float]:
        """Get IV at specific strike from skew."""
        surface = self.current_surface.get(symbol)
        if not surface:
            return None
        
        offset_pct = int(round((strike - spot) / spot * 100))
        
        # Find closest offset in skew
        if offset_pct in surface.skew:
            return surface.skew[offset_pct]
        
        # Interpolate
        offsets = sorted(surface.skew.keys())
        if not offsets:
            return surface.atm_iv
        
        if offset_pct <= offsets[0]:
            return surface.skew[offsets[0]]
        if offset_pct >= offsets[-1]:
            return surface.skew[offsets[-1]]
        
        # Linear interpolation
        for i, o in enumerate(offsets[:-1]):
            if o <= offset_pct <= offsets[i+1]:
                ratio = (offset_pct - o) / (offsets[i+1] - o)
                return surface.skew[o] + ratio * (surface.skew[offsets[i+1]] - surface.skew[o])
        
        return surface.atm_iv
    
    def is_iv_favorable_for_buying(self, symbol: str) -> Tuple[bool, str]:
        """Check if current IV is favorable for options buying."""
        surface = self.current_surface.get(symbol)
        if not surface:
            return True, "No IV data available"
        
        if surface.regime == "HIGH_IV":
            return False, f"IV at {surface.iv_percentile:.0f}th percentile - expensive premiums"
        
        if surface.regime == "CRUSH_RISK":
            return False, "IV crush risk detected - avoid buying"
        
        if surface.regime == "LOW_IV":
            return True, f"IV at {surface.iv_percentile:.0f}th percentile - cheap premiums"
        
        if surface.regime == "EXPANSION_LIKELY":
            return True, "IV expansion likely - buying favorable"
        
        return True, "IV in normal range"
    
    def estimate_iv_crush_impact(
        self,
        symbol: str,
        option: OptionSnapshot,
        crush_pct: float = 0.10
    ) -> float:
        """
        Estimate P&L impact of IV crush.
        
        Args:
            symbol: Symbol
            option: Option to analyze
            crush_pct: Expected IV drop (e.g., 0.10 for 10%)
        
        Returns:
            Expected loss in rupees per lot
        """
        # Vega gives price change per 1% IV move
        # crush_pct is in decimal, so 0.10 = 10%
        iv_drop_pct = crush_pct * 100  # Convert to percentage points
        
        price_drop = option.vega * iv_drop_pct
        
        return round(price_drop, 2)


# Singleton
iv_surface_engine = IVSurfaceEngine()

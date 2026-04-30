"""
TradingModeManager - Indian Market Trading Modes
Manages OPTIONS / EQUITY / FUTURES modes for MarketPilot AI.

Each mode has ALL core features PLUS mode-specific specialized engines.
"""
import json
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from datetime import datetime
from pathlib import Path
from core.event_bus import bus, EventType


class TradingMode(Enum):
    OPTIONS = "OPTIONS"    # Index Options (NIFTY/BANKNIFTY) - Gamma, OI, Max Pain
    EQUITY = "EQUITY"      # Cash Stocks - Support/Resistance, Trend, Breakout
    FUTURES = "FUTURES"    # Index/Stock Futures - Basis, Rollover, Contango


# ============================================================
# CORE ENGINES - Active in ALL modes
# ============================================================
CORE_ENGINES = [
    # Level-01 Order Flow
    "FootprintEngine",
    "LiquidityScanner", 
    "ReplayService",
    # Level-02 Intelligence
    "RegimeClassifier",
    "TrapEngine",
    "IcebergModel",
    "ConsensusEvolution",
    # Level-03 Meta-Intelligence
    "DebateMemory",
    "DecisionExplainer",
    "StrategyFatigue",
    "AgentEvolution",
    "MetaRisk",
    # Core Agents (Universal)
    "Oracle",
    "Predator",
    "Quantum",
    "Galaxy",
    "MarketDataAgent",
    "SentimentAgent",
    "TapeReaderAgent",
    "VolumeFlowAgent",
    "TrapHunterAgent",
    "WhaleAgent",
    "FractalAgent",
]

# ============================================================
# MODE-SPECIFIC ENGINES
# ============================================================

# OPTIONS Mode - Greek-aware, OI-based intelligence
OPTIONS_ENGINES = [
    "GammaEngine",        # Dealer gamma exposure
    "GammaSniperAgent",   # Max pain tracking
    "GammaGhostAgent",    # Gamma flip detection
    "GammaBurstAgent",    # Expansion zones
    "PremiumLabAgent",    # IV/Premium decay
    "OIDecoderAgent",     # OI analysis
    "DeltaSniperAgent",   # Delta-based entries
]

# EQUITY Mode - Price action, trend following
EQUITY_ENGINES = [
    "SupportResistanceEngine",  # Key S/R levels
    "TrendEngine",              # Trend direction + strength
    "BreakoutEngine",           # Breakout detection
    "MovingAverageEngine",      # MA crossovers
    "VolumeProfileEngine",      # Volume at price
    "MomentumEngine",           # RSI/MACD signals
]

# FUTURES Mode - Basis and rollover intelligence
FUTURES_ENGINES = [
    "BasisEngine",        # Spot-Futures basis
    "RolloverEngine",     # Expiry rollover tracking
    "ContangoEngine",     # Contango/Backwardation
    "OpenInterestFlow",   # Futures OI flow
    "SpreadEngine",       # Calendar spreads
    "COTEngine",          # Commitment of Traders
]


@dataclass
class ModeState:
    """Current trading mode state."""
    mode: TradingMode = TradingMode.OPTIONS
    core_engines: List[str] = field(default_factory=list)
    mode_engines: List[str] = field(default_factory=list)
    all_active: List[str] = field(default_factory=list)
    description: str = ""
    timestamp: int = 0
    
    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "core_engines": self.core_engines,
            "mode_engines": self.mode_engines,
            "all_active": self.all_active,
            "description": self.description,
            "time": self.timestamp
        }


MODE_DESCRIPTIONS = {
    TradingMode.OPTIONS: "Index Options (NIFTY/BANKNIFTY) — Gamma, OI, Max Pain, Greek-aware trading",
    TradingMode.EQUITY: "Cash Equity/Stocks — Support/Resistance, Trend, Breakout, Volume Profile",
    TradingMode.FUTURES: "Index/Stock Futures — Basis tracking, Rollover, Contango/Backwardation"
}

MODE_ENGINES_MAP = {
    TradingMode.OPTIONS: OPTIONS_ENGINES,
    TradingMode.EQUITY: EQUITY_ENGINES,
    TradingMode.FUTURES: FUTURES_ENGINES,
}


class TradingModeManager:
    """
    Manages trading modes for Indian markets.
    
    Architecture:
    - CORE features are ALWAYS active (Level-01, 02, 03)
    - Each MODE adds its own specialized engines
    - Switching modes activates different specialized intelligence
    
    Modes:
    - OPTIONS: Greek-aware, OI-based for NIFTY/BANKNIFTY options
    - EQUITY: Price action, trend for cash stocks
    - FUTURES: Basis, rollover for index/stock futures
    """
    def __init__(self):
        self.logger = logging.getLogger("TradingModeManager")
        self.current_mode = TradingMode.OPTIONS
        self.state = ModeState()
        self.db_path = Path("data/trading_mode.json")
        self._load()
        
    def _load(self):
        """Load saved mode preference."""
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    mode_str = data.get('mode', 'OPTIONS')
                    self.current_mode = TradingMode(mode_str)
                self.logger.info(f"Loaded trading mode: {self.current_mode.value}")
        except Exception as e:
            self.logger.error(f"Failed to load trading mode: {e}")
            self.current_mode = TradingMode.OPTIONS
        
        self._update_state()
            
    def _persist(self):
        """Save mode preference."""
        try:
            self.db_path.parent.mkdir(exist_ok=True)
            with open(self.db_path, 'w') as f:
                json.dump({"mode": self.current_mode.value}, f)
        except Exception as e:
            self.logger.error(f"Failed to persist trading mode: {e}")
            
    def _update_state(self):
        """Update the current state based on mode."""
        mode_engines = MODE_ENGINES_MAP.get(self.current_mode, [])
        all_active = CORE_ENGINES + mode_engines
        
        self.state = ModeState(
            mode=self.current_mode,
            core_engines=CORE_ENGINES.copy(),
            mode_engines=mode_engines.copy(),
            all_active=all_active,
            description=MODE_DESCRIPTIONS[self.current_mode],
            timestamp=int(datetime.now().timestamp())
        )
        
    async def set_mode(self, mode: TradingMode) -> ModeState:
        """
        Switch trading mode.
        Broadcasts MODE_CHANGE event to all engines.
        """
        old_mode = self.current_mode
        self.current_mode = mode
        self._update_state()
        self._persist()
        
        self.logger.info(f"🔄 MODE SWITCH: {old_mode.value} → {mode.value}")
        self.logger.info(f"   Core: {len(CORE_ENGINES)} engines (always active)")
        self.logger.info(f"   Mode-Specific: {len(self.state.mode_engines)} engines activated")
        
        # Broadcast mode change
        await bus.publish(EventType.MODE_CHANGE, self.state.to_dict())
        
        return self.state
    
    async def set_mode_by_name(self, mode_name: str) -> ModeState:
        """Set mode by string name."""
        try:
            mode = TradingMode(mode_name.upper())
            return await self.set_mode(mode)
        except ValueError:
            self.logger.error(f"Invalid mode: {mode_name}")
            return self.state
    
    def get_mode(self) -> TradingMode:
        """Get current trading mode."""
        return self.current_mode
    
    def get_state(self) -> dict:
        """Get current mode state."""
        return self.state.to_dict()
    
    def is_engine_active(self, engine_name: str) -> bool:
        """
        Check if an engine should be active in current mode.
        Core engines are ALWAYS active.
        Mode-specific engines are active only in their mode.
        """
        # Core engines always active
        if engine_name in CORE_ENGINES:
            return True
        
        # Check mode-specific engines
        mode_engines = MODE_ENGINES_MAP.get(self.current_mode, [])
        return engine_name in mode_engines
    
    def get_active_engines(self) -> List[str]:
        """Get list of all active engines for current mode."""
        return self.state.all_active
    
    def get_mode_engines(self) -> List[str]:
        """Get list of mode-specific engines only."""
        return self.state.mode_engines
    
    def get_mode_for_display(self) -> dict:
        """Get mode info formatted for UI display."""
        return {
            "current": self.current_mode.value,
            "description": MODE_DESCRIPTIONS[self.current_mode],
            "available": [m.value for m in TradingMode],
            "core_count": len(CORE_ENGINES),
            "mode_count": len(self.state.mode_engines),
            "total_active": len(self.state.all_active)
        }


# Singleton
trading_mode_manager = TradingModeManager()


# Helper functions for engines
def is_mode_active(engine_name: str) -> bool:
    """Quick check if engine should be active in current mode."""
    return trading_mode_manager.is_engine_active(engine_name)


def get_current_mode() -> str:
    """Get current mode as string."""
    return trading_mode_manager.get_mode().value


def is_options_mode() -> bool:
    """Check if in OPTIONS mode."""
    return trading_mode_manager.get_mode() == TradingMode.OPTIONS


def is_equity_mode() -> bool:
    """Check if in EQUITY mode."""
    return trading_mode_manager.get_mode() == TradingMode.EQUITY


def is_futures_mode() -> bool:
    """Check if in FUTURES mode."""
    return trading_mode_manager.get_mode() == TradingMode.FUTURES

"""
Crash Mode Supervisor
The 'General' that overrides strategies during panic.
"""
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
from core.intelligence.fragility_score import fragility_engine, FragilityStatus
from core.gateway import regime_constraints
from core.intelligence.regime_classifier import MarketRegime

class CrashState(Enum):
    NORMAL = "NORMAL"
    FRAGILE = "FRAGILE"   # Defensive
    PANIC = "PANIC"       # Crash Mode
    RECOVERY = "RECOVERY" # Bottom fishing

@dataclass
class CrashStatus:
    state: CrashState
    fragility_score: float
    restrictions: List[str]
    allowed_actions: List[str]

class CrashSupervisor:
    """
    Monitors Fragility and Panic conditions.
    Overrides system behavior to survive crashes.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("CrashSupervisor")
        self.state = CrashState.NORMAL
        self.fragility_status: FragilityStatus = None
        
    def update(self, nifty: float, banknifty: float, vix: float) -> CrashStatus:
        """
        Update state based on market internals.
        """
        # 1. Update Fragility
        self.fragility_status = fragility_engine.update(nifty, banknifty, vix)
        
        # 2. Determine State
        previous_state = self.state
        
        # PANIC logic: VIX > 25 or massive fragility
        if vix > 25.0 or (self.fragility_status.score > 90.0):
            self.state = CrashState.PANIC
            
        # FRAGILE logic: Score > 70
        elif self.fragility_status.is_fragile:
            if self.state != CrashState.PANIC: # Don't downgrade panic easily
                self.state = CrashState.FRAGILE
                
        # RECOVERY logic: VIX dropping from highs (Simulated simply here)
        elif self.state == CrashState.PANIC and vix < 20.0:
            self.state = CrashState.RECOVERY
            
        # NORMAL logic
        else:
             if self.state != CrashState.PANIC and self.state != CrashState.RECOVERY:
                 self.state = CrashState.NORMAL
             elif self.state == CrashState.RECOVERY and vix < 18.0:
                 self.state = CrashState.NORMAL
                 
        if self.state != previous_state:
            self.logger.warning(f"🚨 CRASH MODE SHIFT: {previous_state.name} -> {self.state.name}")
            self._apply_restrictions()
            
        return self.get_status()
    
    def _apply_restrictions(self):
        """
        Apply restrictions to RegimeConstraints based on Crash State.
        """
        if self.state == CrashState.PANIC:
            self.logger.critical("⛔ ENTERING PANIC MODE: Blocking Calls, Reducing Size")
            # Force Regime to PANIC
            regime_constraints.set_override("PANIC", "CrashSupervisor Triggered")
            
        elif self.state == CrashState.FRAGILE:
            self.logger.warning("⚠️ ENTERING FRAGILE MODE: Reducing Size")
            # Force Regime to TRAP/CHOP (Defensive)
            regime_constraints.set_override("TRAP", "Fragility High")
            
        elif self.state == CrashState.NORMAL:
            self.logger.info("✅ MARKET NORMAL: Lifting Restrictions")
            regime_constraints.clear_override()
            
    def get_status(self) -> CrashStatus:
        """Get current status and rules."""
        restrictions = []
        allowed = ["BUY", "SELL"]
        
        if self.state == CrashState.PANIC:
            restrictions = ["NO_BUY_CALLS", "SIZE_25_PCT", "ONE_TRADE_PER_DAY"]
            allowed = ["BUY_PUT", "SELL_CALL"] # Downside only
            
        elif self.state == CrashState.FRAGILE:
            restrictions = ["SIZE_50_PCT", "TIGHT_STOPS"]
            
        return CrashStatus(
            state=self.state,
            fragility_score=self.fragility_status.score if self.fragility_status else 0.0,
            restrictions=restrictions,
            allowed_actions=allowed
        )

# Singleton
crash_supervisor = CrashSupervisor()

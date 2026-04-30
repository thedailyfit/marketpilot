"""
MetaRisk - Self-Regulation & Uncertainty Management
Decides if trading should be allowed at all.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from core.event_bus import bus, EventType


@dataclass
class MetaRiskState:
    """Current meta-risk assessment."""
    trading_allowed: bool = True
    uncertainty_level: int = 0  # 0-100
    allowed_trades_per_hour: int = 10
    block_reasons: List[str] = field(default_factory=list)
    throttle_active: bool = False
    timestamp: int = 0
    
    def to_dict(self) -> dict:
        return {
            "trading_allowed": self.trading_allowed,
            "uncertainty": self.uncertainty_level,
            "allowed_trades": self.allowed_trades_per_hour,
            "block_reasons": self.block_reasons,
            "throttle_active": self.throttle_active,
            "time": self.timestamp
        }


class MetaRisk:
    """
    Self-regulation layer that can:
    - Block trading when conditions are uncertain
    - Throttle trade frequency based on risk
    - Aggregate signals from all meta-intelligence engines
    """
    def __init__(self):
        self.logger = logging.getLogger("MetaRisk")
        self.current_state = MetaRiskState()
        self.trades_this_hour: int = 0
        self.hour_start: int = 0
        self.max_trades_per_hour: int = 10
        self.is_running = False
        
        # Thresholds
        self.dissent_threshold: float = 0.4  # 40% disagreement = concern
        self.regime_confidence_min: float = 60.0
        self.vix_spike_threshold: float = 0.15  # 15% change
        self.fatigue_threshold: int = 50
        self.session_edge_minutes: int = 15
        
    async def on_start(self):
        self.logger.info("Starting Meta-Risk Self-Regulation...")
        self.is_running = True
        self.hour_start = datetime.now().hour
        
    async def on_stop(self):
        self.is_running = False
        self.logger.info("Meta-Risk Stopped")
        
    def should_allow_trade(self, context: dict) -> Tuple[bool, str]:
        """
        Main gate: Decide if a trade should be allowed.
        
        Args:
            context: {
                dissenting_agents: List[str],
                all_agents: List[str],
                regime_confidence: float,
                vix_change_30m: float,
                strategy_fatigue: int,
                minutes_from_open: int,
                minutes_to_close: int
            }
            
        Returns:
            (allowed: bool, reason: str)
        """
        blocks = []
        uncertainty = 0
        
        # 1. Agent Disagreement
        all_agents = context.get('all_agents', [])
        dissenting = context.get('dissenting_agents', [])
        if all_agents:
            dissent_ratio = len(dissenting) / len(all_agents)
            if dissent_ratio > self.dissent_threshold:
                blocks.append(f"High agent disagreement ({dissent_ratio*100:.0f}%)")
                uncertainty += 25
        
        # 2. Regime Uncertainty
        regime_conf = context.get('regime_confidence', 100)
        if regime_conf < self.regime_confidence_min:
            blocks.append(f"Regime unclear ({regime_conf:.0f}%)")
            uncertainty += 20
        
        # 3. VIX Spike
        vix_change = context.get('vix_change_30m', 0)
        if abs(vix_change) > self.vix_spike_threshold:
            blocks.append("VIX spiking — market unstable")
            uncertainty += 25
        
        # 4. Strategy Fatigue
        fatigue = context.get('strategy_fatigue', 0)
        if fatigue > self.fatigue_threshold:
            blocks.append(f"Strategy fatigued ({fatigue})")
            uncertainty += 15
        
        # 5. Session Edge Risk
        mins_from_open = context.get('minutes_from_open', 60)
        mins_to_close = context.get('minutes_to_close', 60)
        if mins_from_open < self.session_edge_minutes:
            blocks.append("Session opening volatility")
            uncertainty += 10
        if mins_to_close < self.session_edge_minutes:
            blocks.append("Session close risk")
            uncertainty += 10
        
        # 6. Trade Frequency Check
        self._update_hour()
        if self.trades_this_hour >= self._get_allowed_trades(uncertainty):
            blocks.append(f"Trade limit reached ({self.trades_this_hour}/{self._get_allowed_trades(uncertainty)})")
        
        # Update state
        uncertainty = min(100, uncertainty)
        allowed = len(blocks) == 0
        
        self.current_state = MetaRiskState(
            trading_allowed=allowed,
            uncertainty_level=uncertainty,
            allowed_trades_per_hour=self._get_allowed_trades(uncertainty),
            block_reasons=blocks,
            throttle_active=uncertainty > 30,
            timestamp=int(datetime.now().timestamp())
        )
        
        if not allowed:
            reason = f"BLOCKED: {'; '.join(blocks)}"
            self.logger.warning(f"🛑 {reason}")
            return False, reason
        
        return True, f"Trade allowed (uncertainty: {uncertainty}%)"
    
    async def gate_trade(self, context: dict) -> Tuple[bool, str]:
        """Gate a trade and emit event if blocked."""
        allowed, reason = self.should_allow_trade(context)
        
        if not allowed:
            await bus.publish(EventType.TRADE_BLOCKED, {
                "reason": reason,
                "blocks": self.current_state.block_reasons,
                "uncertainty": self.current_state.uncertainty_level,
                "time": int(datetime.now().timestamp())
            })
        else:
            self.trades_this_hour += 1
        
        return allowed, reason
    
    def _update_hour(self):
        """Reset hourly counter if hour changed."""
        current_hour = datetime.now().hour
        if current_hour != self.hour_start:
            self.hour_start = current_hour
            self.trades_this_hour = 0
            
    def _get_allowed_trades(self, uncertainty: int) -> int:
        """Calculate allowed trades based on uncertainty."""
        # Reduce max trades as uncertainty increases
        reduction = uncertainty / 100
        return max(1, int(self.max_trades_per_hour * (1 - reduction * 0.7)))
    
    def get_state(self) -> dict:
        """Get current meta-risk state."""
        return self.current_state.to_dict()
    
    def get_uncertainty(self) -> int:
        """Get current uncertainty level."""
        return self.current_state.uncertainty_level
    
    def is_throttled(self) -> bool:
        """Check if trading is throttled."""
        return self.current_state.throttle_active
    
    def set_max_trades(self, max_trades: int):
        """Configure max trades per hour."""
        self.max_trades_per_hour = max_trades
        
    def force_block(self, reason: str):
        """Manually block all trading."""
        self.current_state.trading_allowed = False
        self.current_state.block_reasons = [f"MANUAL: {reason}"]
        self.logger.warning(f"🚫 MANUAL BLOCK: {reason}")
        
    def force_unblock(self):
        """Remove manual block."""
        self.current_state.trading_allowed = True
        self.current_state.block_reasons = []
        self.logger.info("✅ Trading unblocked")


# Singleton
meta_risk = MetaRisk()

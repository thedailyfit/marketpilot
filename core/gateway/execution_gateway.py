"""
Execution Gateway
Single enforcement point for ALL trade execution.
No order reaches broker API without passing this gateway.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

# Import all gates
from .drawdown_guard import drawdown_guard, DrawdownGuard
from .regime_constraints import regime_constraints, RegimeConstraints

# Import governor and risk controls
from core.governor import trading_governor, frequency_regulator
from core.risk import theta_budget_manager, vega_exposure_limit, loss_streak_dampener

# Import intelligence
from core.intelligence.regime_classifier import regime_classifier

# Import zone entry validator (Level-14)
from core.volume import zone_entry_validator


@dataclass
class RiskDecision:
    """
    Gateway decision on trade execution.
    
    action: "ALLOW" or "BLOCK"
    reason: Human-readable explanation
    size_multiplier: Final size modifier (product of all modifiers)
    restrictions: List of active restrictions
    gate_results: Detailed results from each gate
    """
    action: str  # "ALLOW" or "BLOCK"
    reason: str
    size_multiplier: float = 1.0
    restrictions: List[str] = field(default_factory=list)
    gate_results: Dict[str, dict] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "reason": self.reason,
            "size_multiplier": round(self.size_multiplier, 2),
            "restrictions": self.restrictions,
            "gate_results": self.gate_results
        }


class ExecutionGateway:
    """
    Single entry point for ALL trade execution.
    
    Gate Hierarchy:
    1. REGIME GATE - PANIC mode restrictions
    2. DRAWDOWN GATE - Daily/weekly loss limits  
    3. GOVERNOR GATE - Noise, confidence, timing
    4. FREQUENCY GATE - Trades per day
    5. THETA GATE - Decay budget
    6. VEGA GATE - IV crush protection
    7. LOSS STREAK - Size adjustment (never blocks)
    8. ZONE ENTRY - First-touch validation (can block)
    9. IV TREND - Blocks Long Vega in Contracting IV (can block)
    
    NO order can bypass this gateway.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ExecutionGateway")
        self.is_enabled = True
        
        # Track gate bypass attempts
        self.bypass_attempts = 0
        self.blocked_trades = []
    
    def validate(self, trade_idea: Dict[str, Any]) -> RiskDecision:
        """
        Validate a trade idea against ALL risk gates.
        
        Args:
            trade_idea: Must contain at minimum:
                - symbol: str
                - action: BUY/SELL
                - quantity: int
                - strategy: str (optional)
                - theta: float (optional)
                - vega: float (optional)
        
        Returns:
            RiskDecision with ALLOW or BLOCK
        """
        if not self.is_enabled:
            self.logger.warning("⚠️ Gateway DISABLED - allowing trade (DANGEROUS)")
            return RiskDecision(
                action="ALLOW",
                reason="Gateway disabled (unsafe)",
                size_multiplier=1.0
            )
        
        # Validate trade_idea structure
        validation = self._validate_input(trade_idea)
        if not validation["valid"]:
            return RiskDecision(
                action="BLOCK",
                reason=f"INVALID_INPUT: {validation['error']}",
                gate_results={"input_validation": validation}
            )
        
        gate_results = {}
        restrictions = []
        size_multiplier = 1.0
        
        # =========== GATE 1: REGIME ===========
        # Sync regime from classifier (only if no override)
        if not regime_constraints.override_regime:
            regime_state = regime_classifier.get_state()
            regime_constraints.update_regime(regime_state.get("regime", "NORMAL"))
        else:
            regime_state = {"regime": regime_constraints.override_regime.value}
        
        strategy = trade_idea.get("strategy", "BUY_CALL")
        regime_check = regime_constraints.check(strategy)
        gate_results["regime"] = regime_check

        
        if not regime_check["allowed"]:
            return self._block(
                reason=regime_check["reason"],
                gate="REGIME",
                gate_results=gate_results,
                restrictions=[f"REGIME_{regime_check['regime']}"]
            )
        
        # Apply regime size modifier
        size_multiplier *= regime_check["size_modifier"]
        if regime_check.get("warning"):
            restrictions.append(regime_check["warning"])
        
        # =========== GATE 2: DRAWDOWN ===========
        drawdown_check = drawdown_guard.check()
        gate_results["drawdown"] = drawdown_check
        
        if not drawdown_check["allowed"]:
            return self._block(
                reason=drawdown_check["reason"],
                gate="DRAWDOWN",
                gate_results=gate_results,
                restrictions=["DRAWDOWN_LIMIT"]
            )
        
        # Apply drawdown size modifier
        size_multiplier *= drawdown_check.get("size_modifier", 1.0)
        if drawdown_check.get("warning"):
            restrictions.append(drawdown_check["warning"])
        
        # =========== GATE 3: GOVERNOR ===========
        context = {
            "regime": regime_state.get("regime", "UNKNOWN"),
            "atr_percentile": regime_state.get("characteristics", {}).get("atr_percentile", 50),
            "agent_agreement": 0.5  # Default
        }
        
        governor_decision = trading_governor.should_trade_today(context)
        gate_results["governor"] = governor_decision.to_dict()
        
        if not governor_decision.should_trade:
            return self._block(
                reason=f"GOVERNOR: {governor_decision.reason}",
                gate="GOVERNOR",
                gate_results=gate_results,
                restrictions=governor_decision.restrictions
            )
        
        # Apply governor modifiers
        size_multiplier *= governor_decision.max_position_size_pct
        
        # =========== GATE 4: FREQUENCY ===========
        freq_status = frequency_regulator.check()
        gate_results["frequency"] = {
            "trades_today": freq_status.trades_today,
            "max_daily": freq_status.max_daily,
            "over_trading": freq_status.over_trading,
            "cooldown_active": freq_status.cooldown_active
        }
        
        if freq_status.over_trading:
            return self._block(
                reason=f"FREQUENCY: {freq_status.recommendation}",
                gate="FREQUENCY",
                gate_results=gate_results,
                restrictions=["FREQUENCY_LIMIT"]
            )
        
        if freq_status.cooldown_active:
            return self._block(
                reason=f"FREQUENCY: {freq_status.recommendation}",
                gate="FREQUENCY",
                gate_results=gate_results,
                restrictions=["COOLDOWN_ACTIVE"]
            )
        
        # =========== GATE 5: THETA ===========
        order_theta = trade_idea.get("theta", 0)
        order_qty = trade_idea.get("quantity", 1)
        estimated_theta = abs(order_theta) * order_qty
        
        if estimated_theta > 0:
            # Apply regime modifier to theta limit
            theta_modifier = regime_check.get("theta_modifier", 1.0)
            effective_theta = estimated_theta / theta_modifier if theta_modifier > 0 else estimated_theta
            
            theta_check = theta_budget_manager.can_add_position(effective_theta)
            gate_results["theta"] = theta_check
            
            if not theta_check["allowed"]:
                return self._block(
                    reason=f"THETA: {theta_check['reason']}",
                    gate="THETA",
                    gate_results=gate_results,
                    restrictions=["THETA_LIMIT"]
                )
        else:
            gate_results["theta"] = {"skipped": True, "reason": "No theta in trade idea"}
        
        # =========== GATE 6: VEGA ===========
        order_vega = trade_idea.get("vega", 0)
        estimated_vega = abs(order_vega) * order_qty
        
        if estimated_vega > 0:
            # Apply regime modifier to vega limit
            vega_modifier = regime_check.get("vega_modifier", 1.0)
            effective_vega = estimated_vega / vega_modifier if vega_modifier > 0 else estimated_vega
            
            vega_check = vega_exposure_limit.check(effective_vega)
            gate_results["vega"] = vega_check
            
            if not vega_check["allowed"]:
                return self._block(
                    reason=f"VEGA: {vega_check['reason']}",
                    gate="VEGA",
                    gate_results=gate_results,
                    restrictions=["VEGA_LIMIT"]
                )
        else:
            gate_results["vega"] = {"skipped": True, "reason": "No vega in trade idea"}
        
        # =========== GATE 7: LOSS STREAK (adjustment only) ===========
        adjusted_qty = loss_streak_dampener.get_adjusted_quantity(order_qty)
        loss_streak_modifier = adjusted_qty / order_qty if order_qty > 0 else 1.0
        gate_results["loss_streak"] = {
            "original_qty": order_qty,
            "adjusted_qty": adjusted_qty,
            "modifier": loss_streak_modifier
        }
        
        size_multiplier *= loss_streak_modifier
        
        # =========== GATE 8: ZONE ENTRY (First-Touch) ===========
        # Validate entry against institutional zones
        action = trade_idea.get("action", "BUY")
        direction = "LONG" if action == "BUY" else "SHORT"
        current_price = trade_idea.get("entry_price", trade_idea.get("limit_price", 0))
        previous_price = trade_idea.get("previous_price")  # Optional
        
        # Only validate if we have a price
        if current_price > 0:
            zone_entry_check = zone_entry_validator.validate(
                direction=direction,
                current_price=current_price,
                previous_price=previous_price,
                symbol=trade_idea.get("symbol", "NIFTY")
            )
            gate_results["zone_entry"] = zone_entry_check.to_dict()
            
            if not zone_entry_check.allowed:
                return self._block(
                    reason=f"ZONE_ENTRY: {zone_entry_check.reason}",
                    gate="ZONE_ENTRY",
                    gate_results=gate_results,
                    restrictions=["ZONE_ENTRY_BLOCKED"]
                )
                
            # Log successful zone entry
            self.logger.info(
                f"🎯 Zone Entry Validated: {zone_entry_check.reason}"
            )
        else:
            gate_results["zone_entry"] = {"skipped": True, "reason": "No entry_price in trade idea"}
        
        # =========== GATE 9: IV TREND ===========
        # Block Long Vega strategies if IV is crashing (Falling Trend)
        iv_trend = trade_idea.get("iv_trend", "FLAT") # Default to FLAT if unknown
        strategy = trade_idea.get("strategy", "UNKNOWN")
        
        # Identify Long Vega strategies (approximate list)
        long_vega_strategies = ["LONG_CALL", "LONG_PUT", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD", "STRADDLE", "STRANGLE"]
        
        if iv_trend == "FALLING" and strategy in long_vega_strategies:
             # Strict Block on falling IV for long options
             return self._block(
                reason=f"IV TREND: Cannot buy {strategy} in FALLING IV environment.",
                gate="IV_TREND",
                gate_results=gate_results,
                restrictions=["WAIT_FOR_STABLE_IV"]
             )
             
        # Log check
        gate_results["iv_trend"] = {"trend": iv_trend, "strategy": strategy, "status": "PASSED"}

        # =========== ALL GATES PASSED ===========
        final_qty = max(1, int(trade_idea.get("quantity", 1) * size_multiplier))
        
        self.logger.info(
            f"✅ GATEWAY APPROVED: {trade_idea.get('action')} {final_qty}x {trade_idea.get('symbol')} "
            f"(size: {size_multiplier:.0%})"
        )
        
        return RiskDecision(
            action="ALLOW",
            reason="All gates passed",
            size_multiplier=size_multiplier,
            restrictions=restrictions,
            gate_results=gate_results
        )
    
    def _validate_input(self, trade_idea: Dict) -> Dict:
        """Validate trade idea has required fields."""
        required = ["symbol", "action", "quantity"]
        
        if not isinstance(trade_idea, dict):
            return {"valid": False, "error": "trade_idea must be a dict"}
        
        missing = [f for f in required if f not in trade_idea]
        if missing:
            return {"valid": False, "error": f"Missing required fields: {missing}"}
        
        # Validate action
        if trade_idea["action"] not in ["BUY", "SELL"]:
            return {"valid": False, "error": f"Invalid action: {trade_idea['action']}"}
        
        # Validate quantity
        if not isinstance(trade_idea["quantity"], int) or trade_idea["quantity"] <= 0:
            return {"valid": False, "error": f"Invalid quantity: {trade_idea['quantity']}"}
        
        return {"valid": True}
    
    def _block(self, reason: str, gate: str, gate_results: Dict, restrictions: List[str]) -> RiskDecision:
        """Create a BLOCK decision and log it."""
        self.logger.warning(f"🚫 GATEWAY BLOCKED [{gate}]: {reason}")
        
        decision = RiskDecision(
            action="BLOCK",
            reason=reason,
            size_multiplier=0.0,
            restrictions=restrictions,
            gate_results=gate_results
        )
        
        self.blocked_trades.append({
            "timestamp": int(datetime.now().timestamp()),
            "gate": gate,
            "reason": reason
        })
        
        return decision
    
    def record_outcome(self, pnl: float):
        """
        Record trade outcome for drawdown tracking.
        Call this after EVERY trade close.
        """
        drawdown_guard.record_pnl(pnl)
    
    def disable(self, reason: str = "Manual disable"):
        """
        Disable gateway (DANGEROUS).
        Only for emergencies.
        """
        self.logger.error(f"🚨 GATEWAY DISABLED: {reason}")
        self.is_enabled = False
    
    def enable(self):
        """Re-enable gateway."""
        self.is_enabled = True
        self.logger.info("✅ Gateway re-enabled")
    
    def get_status(self) -> Dict:
        """Get comprehensive gateway status."""
        return {
            "enabled": self.is_enabled,
            "regime": regime_constraints.get_status(),
            "drawdown": drawdown_guard.get_status().to_dict(),
            "governor": trading_governor.get_status(),
            "frequency": {
                "trades_today": len(frequency_regulator.trades_today),
                "max_daily": frequency_regulator.max_daily
            },
            "theta": theta_budget_manager.get_status().to_dict(),
            "vega": vega_exposure_limit.get_status().to_dict(),
            "loss_streak": loss_streak_dampener.get_status().to_dict(),
            "blocked_trades_count": len(self.blocked_trades),
            "recent_blocks": self.blocked_trades[-5:] if self.blocked_trades else []
        }


# Singleton
execution_gateway = ExecutionGateway()

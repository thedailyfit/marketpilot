"""
Volume-Based Risk Engine
Places stops behind institutional defense zones, targets before next zone.
"""
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
from .zone_engine import InstitutionalZone, zone_engine
from .profile import ProfileResult, PriceLevel

@dataclass
class RiskPlacement:
    """Complete risk placement with reasoning."""
    stop_loss: float
    take_profit: float
    risk_distance: float      # Entry - SL (absolute)
    reward_distance: float    # TP - Entry (absolute)
    risk_reward_ratio: float
    reasoning: str
    is_valid: bool
    rejection_reason: Optional[str] = None
    
    # Details for audit
    stop_zone_id: Optional[str] = None
    target_zone_id: Optional[str] = None
    stop_behind_hvn: bool = False
    target_before_hvn: bool = False

class VolumeBasedRiskEngine:
    """
    Calculates zone-aware stop loss and take profit levels.
    
    RULES:
    - Stops go BEHIND institutional zones (not inside)
    - Stops NEVER inside LVN (no defense there)
    - Targets go BEFORE next institutional zone
    - If no valid zone → BLOCK trade
    """
    
    def __init__(self):
        self.logger = logging.getLogger("VolumeRiskEngine")
        
        # Minimum zone strength to consider for stop placement
        self.min_zone_strength = 30.0
        
        # Buffer beyond zone boundary (% of entry)
        self.stop_buffer_pct = 0.001  # 0.1%
        self.target_buffer_pct = 0.002  # 0.2%
        
    def calculate(
        self,
        direction: str,  # LONG or SHORT
        entry_price: float,
        zones: Optional[List[InstitutionalZone]] = None,
        profile: Optional[ProfileResult] = None
    ) -> RiskPlacement:
        """
        Calculate zone-aware stop and target.
        
        Args:
            direction: LONG or SHORT
            entry_price: Intended entry price
            zones: List of institutional zones (uses zone_engine if None)
            profile: Volume profile for HVN/LVN checks
            
        Returns:
            RiskPlacement with stop, target, and validity
        """
        # Use global zone engine if zones not provided
        if zones is None:
            zones = zone_engine.get_active_zones()
            
        if not zones:
            return self._reject("No institutional volume zones available for stop placement")
            
        # Separate zones by position relative to entry
        zones_below = sorted(
            [z for z in zones if z.upper_bound < entry_price],
            key=lambda z: z.upper_bound,
            reverse=True  # Nearest first
        )
        
        zones_above = sorted(
            [z for z in zones if z.lower_bound > entry_price],
            key=lambda z: z.lower_bound  # Nearest first
        )
        
        # Calculate based on direction
        if direction.upper() == "LONG":
            return self._calculate_long(entry_price, zones_below, zones_above, profile)
        elif direction.upper() == "SHORT":
            return self._calculate_short(entry_price, zones_below, zones_above, profile)
        else:
            return self._reject(f"Invalid direction: {direction}")
    
    def _calculate_long(
        self,
        entry: float,
        zones_below: List[InstitutionalZone],
        zones_above: List[InstitutionalZone],
        profile: Optional[ProfileResult]
    ) -> RiskPlacement:
        """
        LONG trade risk placement:
        - Stop: Behind nearest zone BELOW entry
        - Target: Before nearest zone ABOVE entry
        """
        reasoning_parts = []
        
        # === STOP LOSS ===
        stop_zone = None
        for zone in zones_below:
            if zone.strength >= self.min_zone_strength:
                stop_zone = zone
                break
                
        if not stop_zone:
            return self._reject("No valid institutional zone below entry for stop placement")
            
        # Place stop BEHIND (below) the lower boundary with buffer
        buffer = entry * self.stop_buffer_pct
        stop_loss = stop_zone.lower_bound - buffer
        
        # Validate stop is not in LVN
        if profile and self._is_in_lvn(stop_loss, profile):
            # Move stop further down to next valid level
            for level in sorted(profile.levels, key=lambda l: l.price, reverse=True):
                if level.price < stop_loss and level.is_hvn:
                    stop_loss = level.price - buffer
                    break
                    
        reasoning_parts.append(
            f"Stop placed behind Zone {stop_zone.zone_id} "
            f"(POC: {stop_zone.poc:.2f}, Strength: {stop_zone.strength:.0f})"
        )
        
        # === TAKE PROFIT ===
        target_zone = None
        for zone in zones_above:
            if zone.strength >= self.min_zone_strength:
                target_zone = zone
                break
                
        if target_zone:
            # Place target BEFORE (below) the lower boundary of resistance zone
            buffer = entry * self.target_buffer_pct
            take_profit = target_zone.lower_bound - buffer
            reasoning_parts.append(
                f"Target before Zone {target_zone.zone_id} "
                f"(POC: {target_zone.poc:.2f})"
            )
        else:
            # No zone above: use default 2:1 R:R
            risk_dist = entry - stop_loss
            take_profit = entry + (risk_dist * 2)
            reasoning_parts.append(
                f"No zone above entry. Using 2:1 R:R target at {take_profit:.2f}"
            )
            
        # Validate target is not inside HVN (stall risk)
        if profile and self._is_in_hvn(take_profit, profile):
            # Reduce target slightly to exit before stall
            take_profit *= 0.995
            reasoning_parts.append("Target adjusted to exit before HVN stall zone")
            
        # Calculate metrics
        risk_distance = abs(entry - stop_loss)
        reward_distance = abs(take_profit - entry)
        rr_ratio = reward_distance / risk_distance if risk_distance > 0 else 0
        
        self.logger.info(
            f"LONG Risk: Entry={entry:.2f} SL={stop_loss:.2f} TP={take_profit:.2f} "
            f"R:R={rr_ratio:.2f}"
        )
        
        return RiskPlacement(
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            risk_distance=round(risk_distance, 2),
            reward_distance=round(reward_distance, 2),
            risk_reward_ratio=round(rr_ratio, 2),
            reasoning=" | ".join(reasoning_parts),
            is_valid=True,
            stop_zone_id=stop_zone.zone_id if stop_zone else None,
            target_zone_id=target_zone.zone_id if target_zone else None,
            stop_behind_hvn=True,
            target_before_hvn=target_zone is not None
        )
    
    def _calculate_short(
        self,
        entry: float,
        zones_below: List[InstitutionalZone],
        zones_above: List[InstitutionalZone],
        profile: Optional[ProfileResult]
    ) -> RiskPlacement:
        """
        SHORT trade risk placement:
        - Stop: Behind nearest zone ABOVE entry
        - Target: Before nearest zone BELOW entry
        """
        reasoning_parts = []
        
        # === STOP LOSS ===
        stop_zone = None
        for zone in zones_above:
            if zone.strength >= self.min_zone_strength:
                stop_zone = zone
                break
                
        if not stop_zone:
            return self._reject("No valid institutional zone above entry for stop placement")
            
        # Place stop BEHIND (above) the upper boundary with buffer
        buffer = entry * self.stop_buffer_pct
        stop_loss = stop_zone.upper_bound + buffer
        
        # Validate stop is not in LVN
        if profile and self._is_in_lvn(stop_loss, profile):
            for level in sorted(profile.levels, key=lambda l: l.price):
                if level.price > stop_loss and level.is_hvn:
                    stop_loss = level.price + buffer
                    break
                    
        reasoning_parts.append(
            f"Stop placed behind Zone {stop_zone.zone_id} "
            f"(POC: {stop_zone.poc:.2f}, Strength: {stop_zone.strength:.0f})"
        )
        
        # === TAKE PROFIT ===
        target_zone = None
        for zone in zones_below:
            if zone.strength >= self.min_zone_strength:
                target_zone = zone
                break
                
        if target_zone:
            # Place target BEFORE (above) the upper boundary of support zone
            buffer = entry * self.target_buffer_pct
            take_profit = target_zone.upper_bound + buffer
            reasoning_parts.append(
                f"Target before Zone {target_zone.zone_id} "
                f"(POC: {target_zone.poc:.2f})"
            )
        else:
            # No zone below: use default 2:1 R:R
            risk_dist = stop_loss - entry
            take_profit = entry - (risk_dist * 2)
            reasoning_parts.append(
                f"No zone below entry. Using 2:1 R:R target at {take_profit:.2f}"
            )
            
        # Validate target is not inside HVN
        if profile and self._is_in_hvn(take_profit, profile):
            take_profit *= 1.005
            reasoning_parts.append("Target adjusted to exit before HVN stall zone")
            
        # Calculate metrics
        risk_distance = abs(stop_loss - entry)
        reward_distance = abs(entry - take_profit)
        rr_ratio = reward_distance / risk_distance if risk_distance > 0 else 0
        
        self.logger.info(
            f"SHORT Risk: Entry={entry:.2f} SL={stop_loss:.2f} TP={take_profit:.2f} "
            f"R:R={rr_ratio:.2f}"
        )
        
        return RiskPlacement(
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            risk_distance=round(risk_distance, 2),
            reward_distance=round(reward_distance, 2),
            risk_reward_ratio=round(rr_ratio, 2),
            reasoning=" | ".join(reasoning_parts),
            is_valid=True,
            stop_zone_id=stop_zone.zone_id if stop_zone else None,
            target_zone_id=target_zone.zone_id if target_zone else None,
            stop_behind_hvn=True,
            target_before_hvn=target_zone is not None
        )
    
    def _is_in_lvn(self, price: float, profile: ProfileResult) -> bool:
        """Check if price falls inside a Low Volume Node."""
        for level in profile.levels:
            # Simple proximity check
            if abs(price - level.price) < 0.5 and level.is_lvn:
                return True
        return False
    
    def _is_in_hvn(self, price: float, profile: ProfileResult) -> bool:
        """Check if price falls inside a High Volume Node."""
        for level in profile.levels:
            if abs(price - level.price) < 0.5 and level.is_hvn:
                return True
        return False
    
    def _reject(self, reason: str) -> RiskPlacement:
        """Create rejection response."""
        self.logger.warning(f"🚫 Risk Placement BLOCKED: {reason}")
        return RiskPlacement(
            stop_loss=0.0,
            take_profit=0.0,
            risk_distance=0.0,
            reward_distance=0.0,
            risk_reward_ratio=0.0,
            reasoning="",
            is_valid=False,
            rejection_reason=reason
        )

# Singleton
volume_risk_engine = VolumeBasedRiskEngine()

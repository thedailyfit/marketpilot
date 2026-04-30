"""
Zone Entry Validator
Enforces First-Touch Entry Logic at Institutional Zones.
"""
import logging
from dataclasses import dataclass
from typing import Optional, List
from .zone_engine import InstitutionalZone, zone_engine
from .manipulation import manipulation_detector

@dataclass 
class ZoneEntryDecision:
    """Zone entry validation result."""
    allowed: bool
    reason: str
    zone_id: Optional[str] = None
    entry_type: Optional[str] = None  # FIRST_TOUCH, BOUNDARY_LONG, BOUNDARY_SHORT
    zone_strength: float = 0.0
    is_fresh: bool = False
    
    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "zone_id": self.zone_id,
            "entry_type": self.entry_type,
            "zone_strength": self.zone_strength,
            "is_fresh": self.is_fresh
        }

class ZoneEntryValidator:
    """
    Validates trade entries against institutional zone rules.
    
    RULES:
    1. LONG: Price must approach zone FROM ABOVE, enter at UPPER boundary
    2. SHORT: Price must approach zone FROM BELOW, enter at LOWER boundary
    3. First-Touch Only: zone.touch_count must be 0
    4. If zone exhausted → BLOCK
    5. If manipulation detected → BLOCK
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ZoneEntryValidator")
        
        # Tolerance for "at boundary" detection (% of price)
        self.boundary_tolerance_pct = 0.002  # 0.2%
        
        # Minimum zone strength to allow entry
        self.min_zone_strength = 40.0
        
    def validate(
        self,
        direction: str,  # LONG or SHORT
        current_price: float,
        previous_price: Optional[float] = None,  # For approach detection
        zones: Optional[List[InstitutionalZone]] = None,
        symbol: str = "NIFTY"
    ) -> ZoneEntryDecision:
        """
        Validate if entry is allowed based on zone rules.
        
        Args:
            direction: LONG or SHORT
            current_price: Current LTP
            previous_price: Previous price (for approach direction)
            zones: List of zones (uses zone_engine if None)
            symbol: Trading symbol
            
        Returns:
            ZoneEntryDecision with allow/block and reason
        """
        # Get zones
        if zones is None:
            zones = zone_engine.get_active_zones()
            
        if not zones:
            return ZoneEntryDecision(
                allowed=False,
                reason="No institutional zones available for entry validation"
            )
            
        # Check manipulation flag
        manip_signal = manipulation_detector.last_signal
        if manip_signal and manip_signal.is_manipulation:
            return ZoneEntryDecision(
                allowed=False,
                reason=f"Manipulation detected: {manip_signal.description}"
            )
        
        # Find relevant zone based on direction
        direction = direction.upper()
        
        if direction == "LONG":
            return self._validate_long_entry(current_price, previous_price, zones)
        elif direction == "SHORT":
            return self._validate_short_entry(current_price, previous_price, zones)
        else:
            return ZoneEntryDecision(
                allowed=False,
                reason=f"Invalid direction: {direction}"
            )
    
    def _validate_long_entry(
        self,
        price: float,
        prev_price: Optional[float],
        zones: List[InstitutionalZone]
    ) -> ZoneEntryDecision:
        """
        LONG Entry Rules:
        - Price approaching zone FROM ABOVE
        - Entry at UPPER boundary of support zone
        - Zone must be fresh (touch_count == 0)
        """
        # Find zones BELOW current price (support zones)
        # Include zones near current price (within tolerance)
        tolerance_pts = price * 0.001  # 0.1% tolerance
        support_zones = sorted(
            [z for z in zones if z.upper_bound <= (price + tolerance_pts)],
            key=lambda z: z.upper_bound,
            reverse=True  # Nearest first
        )
        
        if not support_zones:
            return ZoneEntryDecision(
                allowed=False,
                reason="No support zone below current price for LONG entry"
            )
            
        # Get nearest support zone
        zone = support_zones[0]
        
        # Check zone strength
        if zone.strength < self.min_zone_strength:
            return ZoneEntryDecision(
                allowed=False,
                reason=f"Zone {zone.zone_id} too weak ({zone.strength:.0f}%)",
                zone_id=zone.zone_id,
                zone_strength=zone.strength
            )
        
        # Check first-touch (CRITICAL)
        if zone.touch_count > 0:
            return ZoneEntryDecision(
                allowed=False,
                reason=f"Zone {zone.zone_id} exhausted (touched {zone.touch_count}x)",
                zone_id=zone.zone_id,
                zone_strength=zone.strength,
                is_fresh=False
            )
            
        # Check if price is at upper boundary
        tolerance = price * self.boundary_tolerance_pct
        at_upper_boundary = abs(price - zone.upper_bound) <= tolerance
        
        if not at_upper_boundary:
            distance = abs(price - zone.upper_bound)
            return ZoneEntryDecision(
                allowed=False,
                reason=f"Price not at zone boundary (distance: {distance:.2f}pts)",
                zone_id=zone.zone_id,
                zone_strength=zone.strength,
                is_fresh=zone.is_fresh
            )
            
        # Check approach direction (if previous price provided)
        if prev_price is not None:
            approaching_from_above = prev_price > price
            if not approaching_from_above:
                return ZoneEntryDecision(
                    allowed=False,
                    reason="LONG entry requires approach FROM ABOVE",
                    zone_id=zone.zone_id,
                    zone_strength=zone.strength,
                    is_fresh=zone.is_fresh
                )
        
        # All checks passed!
        self.logger.info(
            f"✅ LONG entry allowed at Zone {zone.zone_id} upper boundary "
            f"({zone.upper_bound:.2f})"
        )
        
        return ZoneEntryDecision(
            allowed=True,
            reason=f"First-touch LONG entry at {zone.zone_id} upper boundary",
            zone_id=zone.zone_id,
            entry_type="FIRST_TOUCH_LONG",
            zone_strength=zone.strength,
            is_fresh=True
        )
    
    def _validate_short_entry(
        self,
        price: float,
        prev_price: Optional[float],
        zones: List[InstitutionalZone]
    ) -> ZoneEntryDecision:
        """
        SHORT Entry Rules:
        - Price approaching zone FROM BELOW
        - Entry at LOWER boundary of resistance zone
        - Zone must be fresh (touch_count == 0)
        """
        # Find zones ABOVE current price (resistance zones)
        # Include zones near current price (within tolerance)
        tolerance_pts = price * 0.001  # 0.1% tolerance
        resistance_zones = sorted(
            [z for z in zones if z.lower_bound >= (price - tolerance_pts)],
            key=lambda z: z.lower_bound  # Nearest first
        )
        
        if not resistance_zones:
            return ZoneEntryDecision(
                allowed=False,
                reason="No resistance zone above current price for SHORT entry"
            )
            
        # Get nearest resistance zone
        zone = resistance_zones[0]
        
        # Check zone strength
        if zone.strength < self.min_zone_strength:
            return ZoneEntryDecision(
                allowed=False,
                reason=f"Zone {zone.zone_id} too weak ({zone.strength:.0f}%)",
                zone_id=zone.zone_id,
                zone_strength=zone.strength
            )
        
        # Check first-touch (CRITICAL)
        if zone.touch_count > 0:
            return ZoneEntryDecision(
                allowed=False,
                reason=f"Zone {zone.zone_id} exhausted (touched {zone.touch_count}x)",
                zone_id=zone.zone_id,
                zone_strength=zone.strength,
                is_fresh=False
            )
            
        # Check if price is at lower boundary
        tolerance = price * self.boundary_tolerance_pct
        at_lower_boundary = abs(price - zone.lower_bound) <= tolerance
        
        if not at_lower_boundary:
            distance = abs(price - zone.lower_bound)
            return ZoneEntryDecision(
                allowed=False,
                reason=f"Price not at zone boundary (distance: {distance:.2f}pts)",
                zone_id=zone.zone_id,
                zone_strength=zone.strength,
                is_fresh=zone.is_fresh
            )
            
        # Check approach direction (if previous price provided)
        if prev_price is not None:
            approaching_from_below = prev_price < price
            if not approaching_from_below:
                return ZoneEntryDecision(
                    allowed=False,
                    reason="SHORT entry requires approach FROM BELOW",
                    zone_id=zone.zone_id,
                    zone_strength=zone.strength,
                    is_fresh=zone.is_fresh
                )
        
        # All checks passed!
        self.logger.info(
            f"✅ SHORT entry allowed at Zone {zone.zone_id} lower boundary "
            f"({zone.lower_bound:.2f})"
        )
        
        return ZoneEntryDecision(
            allowed=True,
            reason=f"First-touch SHORT entry at {zone.zone_id} lower boundary",
            zone_id=zone.zone_id,
            entry_type="FIRST_TOUCH_SHORT",
            zone_strength=zone.strength,
            is_fresh=True
        )

# Singleton
zone_entry_validator = ZoneEntryValidator()

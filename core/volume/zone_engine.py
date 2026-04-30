"""
Institutional Zone Engine
Converts Volume Profile Nodes into actionable Defense Zones.
"""
import logging
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from .profile import ProfileResult, PriceLevel

@dataclass
class InstitutionalZone:
    zone_id: str
    poc: float
    upper_bound: float
    lower_bound: float
    strength: float     # 0-100
    created_at: int
    is_fresh: bool = True # False after first touch
    touch_count: int = 0
    status: str = "ACTIVE" # ACTIVE, DEGRADED, BROKEN
    
    def contains(self, price: float) -> bool:
        return self.lower_bound <= price <= self.upper_bound

class ZoneEngine:
    """
    Identifies zones from profile and manages state.
    """
    def __init__(self):
        self.logger = logging.getLogger("ZoneEngine")
        self.zones: List[InstitutionalZone] = []
        self.zone_counter = 0
        
    def create_zones_from_profile(self, profile: ProfileResult) -> List[InstitutionalZone]:
        """
        Scan profile for major structures (POC, HVN clusters) and create zones.
        """
        new_zones = []
        
        # 1. Primary Zone: The POC
        # Define width based typically on HVN width, simplified to fixed % here
        # Zone = POC +/- 0.2% (Institutional Defense Layer)
        
        poc_price = profile.poc
        half_width = poc_price * 0.002
        
        self.zone_counter += 1
        zone_id = f"ZONE-POC-{self.zone_counter}"
        
        poc_zone = InstitutionalZone(
            zone_id=zone_id,
            poc=poc_price,
            upper_bound=poc_price + half_width,
            lower_bound=poc_price - half_width,
            strength=80.0,
            created_at=int(datetime.now().timestamp()),
            is_fresh=True
        )
        new_zones.append(poc_zone)
        
        # Add to main list
        self.zones.extend(new_zones)
        self.logger.info(f"Created {len(new_zones)} new institutional zones (POC at {poc_price}).")
        return new_zones
        
    def check_interaction(self, price: float) -> Optional[str]:
        """
        Check if price interacts with any zone.
        Returns 'FIRST_TOUCH', 'RETEST', 'BROKEN' or None.
        """
        interaction = None
        
        for zone in self.zones:
            if zone.status == "BROKEN":
                continue
            
            # Simple interaction check
            if zone.contains(price):
                if zone.is_fresh:
                    zone.is_fresh = False
                    zone.touch_count += 1
                    zone.strength -= 10 # Degrade
                    interaction = "FIRST_TOUCH"
                    self.logger.info(f"👉 FIRST TOUCH on Zone {zone.zone_id} [{zone.lower_bound:.2f}-{zone.upper_bound:.2f}]")
                    return interaction # Return immediately on first valid interaction
                else:
                    zone.touch_count += 1
                    zone.strength -= 5
                    if zone.strength < 30:
                        zone.status = "DEGRADED"
                    interaction = "RETEST"
                    
        return interaction

    def get_active_zones(self) -> List[InstitutionalZone]:
        return [z for z in self.zones if z.status == "ACTIVE"]

# Singleton
zone_engine = ZoneEngine()

"""
Zone Entry First-Touch Verification
Tests LONG and SHORT entry scenarios with institutional zones.
"""
import logging
import time
from core.volume.zone_engine import InstitutionalZone
from core.volume.entry_validator import ZoneEntryValidator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def create_mock_zones():
    """Create realistic institutional zones for NIFTY around 22000."""
    ts = int(time.time())
    
    return [
        # Support Zone (for LONG entries)
        InstitutionalZone(
            zone_id="SUPPORT_1",
            poc=21975.0,
            upper_bound=22000.0,  # Entry at this level for LONG
            lower_bound=21950.0,
            strength=75.0,
            created_at=ts,
            is_fresh=True,
            touch_count=0  # FRESH - first touch
        ),
        # Resistance Zone (for SHORT entries)
        InstitutionalZone(
            zone_id="RESIST_1",
            poc=22175.0,
            upper_bound=22200.0,
            lower_bound=22150.0,  # Entry at this level for SHORT
            strength=70.0,
            created_at=ts,
            is_fresh=True,
            touch_count=0  # FRESH - first touch
        ),
        # Exhausted Zone (should reject)
        InstitutionalZone(
            zone_id="EXHAUSTED_1",
            poc=22375.0,
            upper_bound=22400.0,
            lower_bound=22350.0,
            strength=50.0,
            created_at=ts,
            is_fresh=False,
            touch_count=2  # EXHAUSTED - already touched
        ),
    ]

def test_long_first_touch():
    """
    LONG Entry Scenario:
    - Price at SUPPORT_1 upper boundary (22000)
    - Zone is fresh (touch_count=0)
    - Should ALLOW entry
    """
    print("\n" + "="*60)
    print("SCENARIO 1: LONG FIRST-TOUCH ENTRY")
    print("="*60)
    
    validator = ZoneEntryValidator()
    zones = create_mock_zones()
    
    # Price at upper boundary of support zone
    current_price = 22000.5  # At upper boundary (within tolerance)
    prev_price = 22020.0     # Approaching FROM ABOVE
    
    result = validator.validate(
        direction="LONG",
        current_price=current_price,
        previous_price=prev_price,
        zones=zones
    )
    
    print(f"\nCurrent Price: {current_price}")
    print(f"Previous Price: {prev_price}")
    print(f"Direction: LONG")
    print("-" * 40)
    print(f"Allowed: {result.allowed}")
    print(f"Reason: {result.reason}")
    print(f"Zone: {result.zone_id}")
    print(f"Entry Type: {result.entry_type}")
    
    if result.allowed:
        print("\n✅ LONG FIRST-TOUCH ENTRY ALLOWED")
        return True
    else:
        print("\n❌ UNEXPECTEDLY BLOCKED")
        return False

def test_short_first_touch():
    """
    SHORT Entry Scenario:
    - Price at RESIST_1 lower boundary (22150)
    - Zone is fresh (touch_count=0)
    - Should ALLOW entry
    """
    print("\n" + "="*60)
    print("SCENARIO 2: SHORT FIRST-TOUCH ENTRY")
    print("="*60)
    
    validator = ZoneEntryValidator()
    zones = create_mock_zones()
    
    # Price at lower boundary of resistance zone
    current_price = 22150.0  # At lower boundary
    prev_price = 22130.0     # Approaching FROM BELOW
    
    result = validator.validate(
        direction="SHORT",
        current_price=current_price,
        previous_price=prev_price,
        zones=zones
    )
    
    print(f"\nCurrent Price: {current_price}")
    print(f"Previous Price: {prev_price}")
    print(f"Direction: SHORT")
    print("-" * 40)
    print(f"Allowed: {result.allowed}")
    print(f"Reason: {result.reason}")
    print(f"Zone: {result.zone_id}")
    print(f"Entry Type: {result.entry_type}")
    
    if result.allowed:
        print("\n✅ SHORT FIRST-TOUCH ENTRY ALLOWED")
        return True
    else:
        print("\n❌ UNEXPECTEDLY BLOCKED")
        return False

def test_exhausted_zone_rejection():
    """
    REJECTION Scenario:
    - Price approaches EXHAUSTED_1 (touch_count=2)
    - Should BLOCK entry
    """
    print("\n" + "="*60)
    print("SCENARIO 3: EXHAUSTED ZONE REJECTION")
    print("="*60)
    
    validator = ZoneEntryValidator()
    zones = create_mock_zones()
    
    # Price at exhausted zone boundary
    current_price = 22400.0  # At upper boundary of exhausted zone
    prev_price = 22420.0     # Approaching FROM ABOVE
    
    result = validator.validate(
        direction="LONG",
        current_price=current_price,
        previous_price=prev_price,
        zones=zones
    )
    
    print(f"\nCurrent Price: {current_price}")
    print(f"Direction: LONG")
    print(f"Target Zone: EXHAUSTED_1 (touch_count=2)")
    print("-" * 40)
    print(f"Allowed: {result.allowed}")
    print(f"Reason: {result.reason}")
    
    if not result.allowed:
        print("\n✅ CORRECTLY REJECTED EXHAUSTED ZONE")
        return True
    else:
        print("\n❌ SHOULD HAVE BEEN REJECTED!")
        return False

def test_price_not_at_boundary():
    """
    REJECTION Scenario:
    - Price not at zone boundary
    - Should BLOCK entry
    """
    print("\n" + "="*60)
    print("SCENARIO 4: PRICE NOT AT BOUNDARY")
    print("="*60)
    
    validator = ZoneEntryValidator()
    zones = create_mock_zones()
    
    # Price away from any zone boundary
    current_price = 22100.0  # Between zones
    prev_price = 22120.0
    
    result = validator.validate(
        direction="LONG",
        current_price=current_price,
        previous_price=prev_price,
        zones=zones
    )
    
    print(f"\nCurrent Price: {current_price}")
    print(f"Direction: LONG")
    print("-" * 40)
    print(f"Allowed: {result.allowed}")
    print(f"Reason: {result.reason}")
    
    if not result.allowed:
        print("\n✅ CORRECTLY REJECTED (price not at boundary)")
        return True
    else:
        print("\n❌ SHOULD HAVE BEEN REJECTED!")
        return False

def test_no_zones():
    """
    REJECTION Scenario:
    - No zones available
    - Should BLOCK entry
    """
    print("\n" + "="*60)
    print("SCENARIO 5: NO ZONES AVAILABLE")
    print("="*60)
    
    validator = ZoneEntryValidator()
    
    result = validator.validate(
        direction="LONG",
        current_price=22100.0,
        zones=[]  # Empty!
    )
    
    print(f"\nZones: EMPTY")
    print("-" * 40)
    print(f"Allowed: {result.allowed}")
    print(f"Reason: {result.reason}")
    
    if not result.allowed:
        print("\n✅ CORRECTLY REJECTED (no zones)")
        return True
    else:
        print("\n❌ SHOULD HAVE BEEN REJECTED!")
        return False

if __name__ == "__main__":
    print("="*60)
    print("ZONE ENTRY FIRST-TOUCH VERIFICATION")
    print("="*60)
    
    results = []
    results.append(("LONG First-Touch", test_long_first_touch()))
    results.append(("SHORT First-Touch", test_short_first_touch()))
    results.append(("Exhausted Zone Rejection", test_exhausted_zone_rejection()))
    results.append(("Price Not At Boundary", test_price_not_at_boundary()))
    results.append(("No Zones Available", test_no_zones()))
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎯 ALL SCENARIOS VERIFIED — FIRST-TOUCH ENTRY IS LIVE!")
    else:
        print("\n⚠️ SOME SCENARIOS FAILED — REVIEW REQUIRED")

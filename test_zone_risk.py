"""
Zone-Aware Risk Placement Verification
Tests LONG and SHORT scenarios with institutional volume zones.
"""
import logging
from core.volume.zone_engine import InstitutionalZone
from core.volume.profile import ProfileResult, PriceLevel
from core.volume.risk_engine import VolumeBasedRiskEngine

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def create_mock_zones():
    """Create realistic institutional zones for NIFTY around 22000."""
    import time
    ts = int(time.time())
    
    return [
        InstitutionalZone(
            zone_id="ZONE_1",
            poc=21825.0,
            upper_bound=21850.0,
            lower_bound=21800.0,
            strength=85.0,
            created_at=ts,
            is_fresh=True,
            touch_count=0
        ),
        InstitutionalZone(
            zone_id="ZONE_2",
            poc=21975.0,
            upper_bound=22000.0,
            lower_bound=21950.0,
            strength=65.0,
            created_at=ts,
            is_fresh=True,
            touch_count=1
        ),
        InstitutionalZone(
            zone_id="ZONE_3",
            poc=22175.0,
            upper_bound=22200.0,
            lower_bound=22150.0,
            strength=75.0,
            created_at=ts,
            is_fresh=True,
            touch_count=0
        ),
        InstitutionalZone(
            zone_id="ZONE_4",
            poc=22375.0,
            upper_bound=22400.0,
            lower_bound=22350.0,
            strength=90.0,
            created_at=ts,
            is_fresh=True,
            touch_count=0
        ),
    ]

def create_mock_profile():
    """Create mock volume profile with HVN/LVN markers."""
    levels = [
        PriceLevel(price=21825.0, volume=5000000, is_hvn=True, is_lvn=False),
        PriceLevel(price=21900.0, volume=500000, is_hvn=False, is_lvn=True),  # LVN
        PriceLevel(price=21975.0, volume=3500000, is_hvn=True, is_lvn=False),
        PriceLevel(price=22050.0, volume=400000, is_hvn=False, is_lvn=True),  # LVN
        PriceLevel(price=22175.0, volume=4200000, is_hvn=True, is_lvn=False),
        PriceLevel(price=22300.0, volume=600000, is_hvn=False, is_lvn=True),  # LVN
        PriceLevel(price=22375.0, volume=6000000, is_hvn=True, is_lvn=False),
    ]
    
    return ProfileResult(
        poc=22175.0,
        vah=22350.0,
        val=21850.0,
        levels=levels,
        total_volume=20000000
    )

def test_long_scenario():
    """
    LONG Trade Scenario:
    - Entry at 22100 (between zones)
    - Should place SL behind Zone 2 (21950-22000)
    - Should place TP before Zone 3 (22150-22200)
    """
    print("\n" + "="*60)
    print("SCENARIO 1: LONG TRADE")
    print("="*60)
    
    engine = VolumeBasedRiskEngine()
    zones = create_mock_zones()
    profile = create_mock_profile()
    
    entry_price = 22100.0
    
    result = engine.calculate(
        direction="LONG",
        entry_price=entry_price,
        zones=zones,
        profile=profile
    )
    
    print(f"\nEntry Price: {entry_price}")
    print(f"Direction: LONG")
    print("-" * 40)
    
    if result.is_valid:
        print(f"✅ Stop Loss: {result.stop_loss}")
        print(f"✅ Take Profit: {result.take_profit}")
        print(f"Risk Distance: {result.risk_distance}")
        print(f"Reward Distance: {result.reward_distance}")
        print(f"R:R Ratio: {result.risk_reward_ratio}")
        print(f"\nReasoning: {result.reasoning}")
        print(f"Stop Zone: {result.stop_zone_id}")
        print(f"Target Zone: {result.target_zone_id}")
        
        # Validate
        assert result.stop_loss < entry_price, "SL must be below entry for LONG"
        assert result.take_profit > entry_price, "TP must be above entry for LONG"
        assert result.stop_loss < 21950, "SL must be behind Zone 2 lower boundary"
        assert result.take_profit < 22150, "TP must be before Zone 3 lower boundary"
        print("\n✅ ALL LONG VALIDATIONS PASSED")
    else:
        print(f"❌ REJECTED: {result.rejection_reason}")
        return False
    
    return True

def test_short_scenario():
    """
    SHORT Trade Scenario:
    - Entry at 22100 (between zones)
    - Should place SL behind Zone 3 (22150-22200)
    - Should place TP before Zone 2 (21950-22000)
    """
    print("\n" + "="*60)
    print("SCENARIO 2: SHORT TRADE")
    print("="*60)
    
    engine = VolumeBasedRiskEngine()
    zones = create_mock_zones()
    profile = create_mock_profile()
    
    entry_price = 22100.0
    
    result = engine.calculate(
        direction="SHORT",
        entry_price=entry_price,
        zones=zones,
        profile=profile
    )
    
    print(f"\nEntry Price: {entry_price}")
    print(f"Direction: SHORT")
    print("-" * 40)
    
    if result.is_valid:
        print(f"✅ Stop Loss: {result.stop_loss}")
        print(f"✅ Take Profit: {result.take_profit}")
        print(f"Risk Distance: {result.risk_distance}")
        print(f"Reward Distance: {result.reward_distance}")
        print(f"R:R Ratio: {result.risk_reward_ratio}")
        print(f"\nReasoning: {result.reasoning}")
        print(f"Stop Zone: {result.stop_zone_id}")
        print(f"Target Zone: {result.target_zone_id}")
        
        # Validate
        assert result.stop_loss > entry_price, "SL must be above entry for SHORT"
        assert result.take_profit < entry_price, "TP must be below entry for SHORT"
        assert result.stop_loss > 22200, "SL must be behind Zone 3 upper boundary"
        assert result.take_profit > 22000, "TP must be before Zone 2 upper boundary"
        print("\n✅ ALL SHORT VALIDATIONS PASSED")
    else:
        print(f"❌ REJECTED: {result.rejection_reason}")
        return False
    
    return True

def test_no_zones_rejection():
    """
    REJECTION Scenario:
    - No zones available → Trade must be BLOCKED
    """
    print("\n" + "="*60)
    print("SCENARIO 3: NO ZONES (REJECTION)")
    print("="*60)
    
    engine = VolumeBasedRiskEngine()
    
    result = engine.calculate(
        direction="LONG",
        entry_price=22100.0,
        zones=[],  # Empty!
        profile=None
    )
    
    print(f"\nEntry Price: 22100")
    print(f"Zones: EMPTY")
    print("-" * 40)
    
    if not result.is_valid:
        print(f"✅ CORRECTLY REJECTED: {result.rejection_reason}")
        return True
    else:
        print(f"❌ SHOULD HAVE BEEN REJECTED!")
        return False

if __name__ == "__main__":
    print("="*60)
    print("ZONE-AWARE RISK PLACEMENT VERIFICATION")
    print("="*60)
    
    results = []
    results.append(("LONG Scenario", test_long_scenario()))
    results.append(("SHORT Scenario", test_short_scenario()))
    results.append(("No Zones Rejection", test_no_zones_rejection()))
    
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
        print("\n🎯 ALL SCENARIOS VERIFIED — ZONE-AWARE RISK IS LIVE!")
    else:
        print("\n⚠️ SOME SCENARIOS FAILED — REVIEW REQUIRED")

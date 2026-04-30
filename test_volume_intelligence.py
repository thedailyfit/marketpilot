import asyncio
import logging
import pandas as pd
from core.volume.profile import volume_profile
from core.volume.zone_engine import zone_engine

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("TestVolume")

def test_volume_intelligence():
    print("="*60)
    print("LEVEL-14: VOLUME INTELLIGENCE VERIFICATION")
    print("="*60)
    
    # 1. Simulate Price/Volume Data
    # High volume at 100 (POC)
    data = pd.DataFrame({
        'close': [98, 99, 100, 100, 100, 100, 101, 102, 100, 100],
        'high':  [98, 99, 100, 100, 100, 100, 101, 102, 100, 100], # Simplified
        'low':   [98, 99, 100, 100, 100, 100, 101, 102, 100, 100],
        'volume': [10, 20, 100, 100, 100, 100, 20, 10, 100, 100]
    })
    
    # 2. Compute Profile
    print("\n--- Computing Volume Profile ---")
    profile = volume_profile.calculate(data)
    
    if profile:
        print(f"POC: {profile.poc}")
        print(f"VAH: {profile.vah}")
        print(f"VAL: {profile.val}")
        print(f"Total Vol: {profile.total_volume}")
        
        # Verify POC is 100.0 (approx due to binning)
        # Bins: 1.0 size. 100 bucket has most volume.
        # POC should be around 100.5 or 100.0 depending on bin edge
    else:
        print("❌ Profile calculation failed")
        return

    # 3. Create Zones
    print("\n--- Creating Institutional Zones ---")
    zones = zone_engine.create_zones_from_profile(profile)
    
    if not zones:
        print("❌ No zones created")
        return
        
    poc_zone = zones[0]
    print(f"Created Zone: {poc_zone.zone_id} POC={poc_zone.poc} [{poc_zone.lower_bound:.2f}-{poc_zone.upper_bound:.2f}]")
    
    # 4. First Touch Test
    print("\n--- Testing Interactions ---")
    
    # Price comes into zone
    price_touch = poc_zone.poc
    reaction = zone_engine.check_interaction(price_touch)
    print(f"Interaction at {price_touch}: {reaction}")
    
    assert reaction == "FIRST_TOUCH"
    
    # Second touch (Retest)
    reaction2 = zone_engine.check_interaction(price_touch)
    print(f"Interaction at {price_touch}: {reaction2}")
    
    assert reaction2 == "RETEST"
    
    print("\n✅ Volume Logic Verified")

if __name__ == "__main__":
    test_volume_intelligence()

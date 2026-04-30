"""
Confluence Engine Verification
Tests Institutional Confluence scoring logic.
"""
import logging
from core.intelligence.confluence_engine import confluence_engine
from core.volume.zone_engine import InstitutionalZone
from core.intelligence.gamma_engine import GammaState

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def test_confluence_logic():
    print("="*60)
    print("CONFLUENCE ENGINE VERIFICATION (Level-14 Ext)")
    print("="*60)
    
    # Setup Dummies
    poc = 22000.0
    fresh_zone = InstitutionalZone(
        zone_id="Z1", poc=poc, upper_bound=22010.0, lower_bound=21990.0,
        strength=80.0, created_at=0, is_fresh=True
    )
    
    gamma_positive = GammaState(
        spot=22000.0, max_pain=22500.0, gamma_flip=21800.0,
        zone="POSITIVE", pressure="PINNING", net_gamma=5000000,
        timestamp=100
    )
    
    gamma_negative = GammaState(
        spot=22000.0, max_pain=22500.0, gamma_flip=22100.0,
        zone="NEGATIVE", pressure="EXPANSION", net_gamma=-5000000,
        timestamp=100
    )

    # SCENARIO 1: Perfect Long Setup
    # Spot is right on the POC (22000). Market is in Negative Gamma (Expansion).
    # Being on the POC gives 50 + 15 (Proximity) = 65.
    # Long in Negative Gamma = +25. Total = 90.
    print("\n[SCENARIO 1] ALIGNED LONG (POC Bount + Env. Expansion)")
    spot = 22000.0
    report1 = confluence_engine.evaluate(
        spot_price=spot, direction="LONG", 
        active_zones=[fresh_zone], gamma_state=gamma_negative
    )
    print(f"Score: {report1.score}")
    for r in report1.reasons:
        print(f"  {r}")
    if report1.score >= 80:
         print("✅ PASS: Correctly scored a high-confluence aligned trade.")
    else:
         print("❌ FAIL: Score too low.")

    # SCENARIO 2: Conflicting Short
    # Shorting at a support zone (22000 POC) during POSITIVE Gamma pinning.
    print("\n[SCENARIO 2] CONFLICTING SHORT (Shorting Support in Pinning Regime)")
    spot = 22000.0
    report2 = confluence_engine.evaluate(
        spot_price=spot, direction="SHORT", 
        active_zones=[fresh_zone], gamma_state=gamma_positive
    )
    print(f"Score: {report2.score}")
    for r in report2.reasons:
        print(f"  {r}")
    if report2.score < 50:
         print("✅ PASS: Correctly deducted points for conflict.")
    else:
         print("❌ FAIL: Score too high for conflicting trade.")

    # SCENARIO 3: No Man's Land
    # Far from any zone. Neutral/Missing Gamma.
    print("\n[SCENARIO 3] NO MAN'S LAND (No Zone, Empty Gamma)")
    spot = 22200.0
    report3 = confluence_engine.evaluate(
        spot_price=spot, direction="LONG", 
        active_zones=[fresh_zone], gamma_state=None
    )
    print(f"Score: {report3.score}")
    for r in report3.reasons:
        print(f"  {r}")
    if report3.score < 30:
         print("✅ PASS: Kept score low for random entry.")
    else:
         print("❌ FAIL: Scored too high for empty setup.")


    print("\n✅ Confluence Engine Logic Verification Complete.")

if __name__ == "__main__":
    test_confluence_logic()

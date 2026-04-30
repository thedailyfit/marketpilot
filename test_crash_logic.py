import asyncio
import logging
from core.governor.crash_supervisor import crash_supervisor, CrashState
from core.gateway import regime_constraints
from core.intelligence.fragility_score import fragility_engine

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("TestCrashLogic")

def print_status(phase):
    status = crash_supervisor.get_status()
    print(f"\n--- {phase} ---")
    print(f"State: {status.state.name}")
    print(f"Fragility Score: {status.fragility_score}")
    print(f"Restrictions: {status.restrictions}")
    print(f"Allowed Actions: {status.allowed_actions}")
    
    # Check Regime Constraints
    regime_status = regime_constraints.get_status()
    print(f"Regime Override: {regime_status['is_override']} ({regime_status['regime']})")

async def test_crash_logic():
    print("="*60)
    print("LEVEL-10: CRASH LOGIC VERIFICATION")
    print("="*60)
    
    # ---------------------------------------------------------
    # Phase 1: NORMAL MARKET
    # Price rising, VIX stable
    # ---------------------------------------------------------
    start_nifty = 10000
    start_bn = 20000
    
    # Simulate 20 ticks of normal trend
    for i in range(20):
        nifty = start_nifty + (i * 10)
        bn = start_bn + (i * 20)
        vix = 15.0
        crash_supervisor.update(nifty, bn, vix)
        
    print_status("PHASE 1: NORMAL MARKET (Expect NORMAL)")
    assert crash_supervisor.state == CrashState.NORMAL
    
    # ---------------------------------------------------------
    # Phase 2: FRAGILITY (VIX Divergence)
    # Price making highs, VIX rising fast
    # ---------------------------------------------------------
    # Continue trend but spike VIX
    for i in range(10):
        nifty = 10200 + (i * 10) # Higher highs
        bn = 20400 + (i * 20)
        vix = 15.0 + (i * 0.5)   # VIX rising to 20
        crash_supervisor.update(nifty, bn, vix)
        
    print_status("PHASE 2: FRAGILITY (Expect FRAGILE)")
    # Note: VIX divergence + Rising VIX should trigger fragility
    
    # ---------------------------------------------------------
    # Phase 3: PANIC CRASH
    # VIX explodes > 25
    # ---------------------------------------------------------
    crash_supervisor.update(10300, 20600, 26.0) # VIX > 25
    
    print_status("PHASE 3: PANIC (Expect PANIC)")
    assert crash_supervisor.state == CrashState.PANIC
    assert regime_constraints.get_active_regime().value == "PANIC"
    
    # ---------------------------------------------------------
    # Phase 4: RECOVERY
    # VIX crushed < 20
    # ---------------------------------------------------------
    crash_supervisor.update(10300, 20600, 18.0)
    
    print_status("PHASE 4: RECOVERY (Expect RECOVERY/NORMAL)")
    # Logic: From Panic, if VIX < 20, go to Recovery
    assert crash_supervisor.state == CrashState.RECOVERY
    
    # ---------------------------------------------------------
    # Phase 5: BACK TO NORMAL
    # VIX < 18
    # ---------------------------------------------------------
    crash_supervisor.update(10300, 20600, 16.0)
    
    print_status("PHASE 5: BACK TO NORMAL")
    assert crash_supervisor.state == CrashState.NORMAL
    assert not regime_constraints.override_regime

if __name__ == "__main__":
    asyncio.run(test_crash_logic())

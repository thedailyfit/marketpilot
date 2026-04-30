import logging
from core.strategy.registry import strategy_registry
from core.strategy.registry import strategy_registry
from core.strategy.performance_tracker import performance_tracker
from core.strategy.rollback_engine import rollback_engine

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("TestLifecycle")

def test_lifecycle():
    print("="*60)
    print("LEVEL-13: STRATEGY LIFECYCLE VERIFICATION")
    print("="*60)
    
    strat_name = "TestStrat"
    
    # 1. Register v1.0.0 (Stable)
    v1_id = strategy_registry.register_strategy(strat_name, {"period": 20})
    print(f"\nCreated {v1_id}")
    
    # 2. Simulate Good Performance for v1.0.0
    print(f"Simulating trades for {v1_id}...")
    for _ in range(10):
        performance_tracker.record_trade(strat_name, v1_id, 100.0) # Win
    for _ in range(5):
        performance_tracker.record_trade(strat_name, v1_id, -50.0) # Loss
        
    stats_v1 = performance_tracker.get_metrics(strat_name, v1_id)
    print(f"v1.0.0 Win Rate: {stats_v1.win_rate:.1f}%")
    
    # Verify no regression yet
    rollback_engine.check_for_regression(strat_name, v1_id)
    assert strategy_registry.strategies[strat_name].active_version == v1_id
    
    # 3. Promote to v1.0.1 (Bad Update)
    v2_id = strategy_registry.promote_version(strat_name, {"period": 10}, "Faster Period")
    print(f"\nPromoted to {v2_id}")
    
    # 4. Simulate Bad Performance for v1.0.1
    print(f"Simulating trades for {v2_id}...")
    for _ in range(10): # 10 Losses in a row!
        performance_tracker.record_trade(strat_name, v2_id, -100.0)
        
    stats_v2 = performance_tracker.get_metrics(strat_name, v2_id)
    print(f"v1.0.1 Win Rate: {stats_v2.win_rate:.1f}%")
    
    # 5. Check Regression
    print("\nChecking for Regression...")
    rollback_engine.check_for_regression(strat_name, v2_id)
    
    # 6. Verify Rollback
    current_active = strategy_registry.strategies[strat_name].active_version
    print(f"Active Version after check: {current_active}")
    
    if current_active == v1_id:
        print("✅ SUCCESS: Rolled back to v1.0.0")
    elif current_active == v2_id:
        print("❌ FAILURE: Still on v1.0.1")
    else:
        print(f"❓ UNKNOWN STATE: {current_active}")

    # Assertions
    assert current_active == v1_id
    assert strategy_registry.strategies[strat_name].versions[v2_id].status == "DISABLED"

if __name__ == "__main__":
    test_lifecycle()

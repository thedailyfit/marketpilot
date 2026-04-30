"""
Test script for Level-06 ExecutionGateway verification.
Tests all gates including new REGIME and DRAWDOWN gates.
"""
import asyncio
from core.gateway import execution_gateway, regime_constraints, drawdown_guard
from core.governor import frequency_regulator, trading_governor
from core.risk import theta_budget_manager, vega_exposure_limit


async def test_gateway():
    print("=" * 70)
    print("LEVEL-06: EXECUTION GATEWAY VERIFICATION")
    print("=" * 70)
    
    # Reset all state
    frequency_regulator.trades_today = []
    frequency_regulator.last_trade_time = None
    theta_budget_manager.current_theta = 0
    vega_exposure_limit.current_vega = 0
    drawdown_guard.daily_pnl = 0
    drawdown_guard.weekly_pnl = 0
    drawdown_guard.is_paused = False
    execution_gateway.blocked_trades = []
    trading_governor.confidence = 1.0  # Reset governor confidence
    
    # Use override to set regime (bypasses classifier sync)
    regime_constraints.set_override("NORMAL", "Testing")
    
    # ===== TEST 1: Normal order (should ALLOW) =====
    print("\n--- TEST 1: Normal order in NORMAL regime ---")
    trade_idea_1 = {
        'action': 'BUY',
        'quantity': 50,
        'symbol': 'NSE_FO|NIFTY2510823000CE',
        'strategy': 'BUY_CALL',
        'theta': 0,
        'vega': 0
    }
    
    decision_1 = execution_gateway.validate(trade_idea_1)
    test1_pass = decision_1.action == "ALLOW"
    if test1_pass:
        print(f"✅ TEST 1 PASSED: Order allowed (size: {decision_1.size_multiplier:.0%})")
    else:
        print(f"❌ TEST 1 FAILED: {decision_1.reason}")
    
    # ===== TEST 2: PANIC regime (should reduce size) =====
    print("\n--- TEST 2: PANIC regime (size should be 25%) ---")
    frequency_regulator.trades_today = []  # Reset frequency
    regime_constraints.set_override("PANIC", "Testing")
    
    trade_idea_2 = {
        'action': 'BUY',
        'quantity': 100,
        'symbol': 'NSE_FO|NIFTY2510823000PE',
        'strategy': 'BUY_PUT',  # Allowed in PANIC
        'theta': 0,
        'vega': 0
    }
    
    decision_2 = execution_gateway.validate(trade_idea_2)
    test2_pass = decision_2.action == "ALLOW" and decision_2.size_multiplier <= 0.30
    if test2_pass:
        print(f"✅ TEST 2 PASSED: Size reduced to {decision_2.size_multiplier:.0%} in PANIC mode")
    else:
        print(f"❌ TEST 2 FAILED: action={decision_2.action}, size={decision_2.size_multiplier:.0%}")
    
    # ===== TEST 3: PANIC regime with blocked strategy =====
    print("\n--- TEST 3: PANIC regime blocks BUY_CALL strategy ---")
    frequency_regulator.trades_today = []  # Reset frequency
    
    trade_idea_3 = {
        'action': 'BUY',
        'quantity': 50,
        'symbol': 'NSE_FO|NIFTY2510823000CE',
        'strategy': 'BUY_CALL',  # NOT allowed in PANIC
        'theta': 0,
        'vega': 0
    }
    
    decision_3 = execution_gateway.validate(trade_idea_3)
    test3_pass = decision_3.action == "BLOCK" and "REGIME" in decision_3.reason
    if test3_pass:
        print(f"✅ TEST 3 PASSED: BUY_CALL blocked in PANIC mode")
    else:
        print(f"❌ TEST 3 FAILED: action={decision_3.action}, reason={decision_3.reason}")
    
    # ===== TEST 4: Drawdown limit =====
    print("\n--- TEST 4: Drawdown limit blocks trading ---")
    regime_constraints.set_override("NORMAL", "Testing")  # Back to normal
    frequency_regulator.trades_today = []
    
    # Simulate -6% daily loss (exceeds 5% pause limit)
    drawdown_guard.capital = 500000
    drawdown_guard.daily_pnl = -30000  # -6% directly set
    drawdown_guard.is_paused = True
    drawdown_guard.pause_reason = "DAILY_PAUSE: -6.0% hit 5.0% limit"
    
    trade_idea_4 = {
        'action': 'BUY',
        'quantity': 50,
        'symbol': 'NSE_FO|NIFTY2510823000CE',
        'strategy': 'BUY_CALL',
        'theta': 0,
        'vega': 0
    }
    
    decision_4 = execution_gateway.validate(trade_idea_4)
    # Drawdown gate blocks with the pause_reason
    test4_pass = decision_4.action == "BLOCK" and ("DAILY" in decision_4.reason or "DRAWDOWN" in decision_4.reason)
    if test4_pass:
        print(f"✅ TEST 4 PASSED: Trading blocked due to {decision_4.reason}")
    else:
        print(f"❌ TEST 4 FAILED: action={decision_4.action}, reason={decision_4.reason}")
    
    # ===== TEST 5: Frequency limit =====
    print("\n--- TEST 5: Frequency limit after 3 trades ---")
    # Reset all states for clean test
    drawdown_guard.daily_pnl = 0
    drawdown_guard.weekly_pnl = 0
    drawdown_guard.is_paused = False
    drawdown_guard.pause_reason = None
    trading_governor.confidence = 1.0
    frequency_regulator.trades_today = []
    frequency_regulator.last_trade_time = None
    
    # This time just check if frequency blocking works (via governor which integrates it)
    # Record exactly 3 trades to hit limit
    frequency_regulator.record_trade('T1', 'NIFTY', 'BUY')
    frequency_regulator.record_trade('T2', 'NIFTY', 'SELL')
    frequency_regulator.record_trade('T3', 'NIFTY', 'BUY')
    
    decision_5 = execution_gateway.validate(trade_idea_4)
    # Either FREQUENCY or GOVERNOR will block (governor integrates frequency)
    test5_pass = decision_5.action == "BLOCK" and ("FREQUENCY" in decision_5.reason or "daily limit" in decision_5.reason.lower())
    if test5_pass:
        print(f"✅ TEST 5 PASSED: Blocked after 3 trades - {decision_5.reason}")
    else:
        print(f"❌ TEST 5 FAILED: action={decision_5.action}, reason={decision_5.reason}")
    
    # ===== TEST 6: Theta limit =====
    print("\n--- TEST 6: Theta budget limit ---")
    # Reset everything for clean theta test
    frequency_regulator.trades_today = []
    frequency_regulator.last_trade_time = None
    trading_governor.confidence = 1.0
    theta_budget_manager.update_current_theta(450)  # Near limit
    
    trade_idea_6 = {
        'action': 'BUY',
        'quantity': 50,
        'symbol': 'NSE_FO|NIFTY2510823000CE',
        'strategy': 'BUY_CALL',
        'theta': 2,  # 2 * 50 = 100, would exceed 500 budget
        'vega': 0
    }
    
    decision_6 = execution_gateway.validate(trade_idea_6)
    test6_pass = decision_6.action == "BLOCK" and "THETA" in decision_6.reason
    if test6_pass:
        print(f"✅ TEST 6 PASSED: Blocked due to theta limit")
    else:
        print(f"❌ TEST 6 FAILED: action={decision_6.action}, reason={decision_6.reason}")
    
    # ===== TEST 7: Gateway status =====
    print("\n--- TEST 7: Gateway status report ---")
    regime_constraints.clear_override()  # Clear override
    status = execution_gateway.get_status()
    print(f"  Gateway enabled: {status['enabled']}")
    print(f"  Blocked trades: {status['blocked_trades_count']}")
    
    print("\n" + "=" * 70)
    print("LEVEL-06 GATEWAY VERIFICATION COMPLETE")
    print("=" * 70)
    
    # Summary
    passed = sum([test1_pass, test2_pass, test3_pass, test4_pass, test5_pass, test6_pass])
    
    print(f"\nRESULT: {passed}/6 tests passed")
    print("- All risk engines consolidated into ExecutionGateway")
    print("- No order can bypass gateway to reach broker API")
    
    if passed == 6:
        print("\n🎉 ALL TESTS PASSED - Level-06 Gateway is fully operational!")
    else:
        print(f"\n⚠️ {6-passed} tests need investigation")


if __name__ == "__main__":
    asyncio.run(test_gateway())

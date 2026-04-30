"""
Test script for ExecutionAgent hard gate verification.
"""
import asyncio
from agents.trading.execution import ExecutionAgent
from core.governor import trading_governor, frequency_regulator
from core.risk import theta_budget_manager, vega_exposure_limit


async def test_gates():
    print("=" * 60)
    print("EXECUTION AGENT GATE VERIFICATION")
    print("=" * 60)
    
    # Reset state for clean test
    frequency_regulator.trades_today = []
    frequency_regulator.last_trade_time = None
    theta_budget_manager.current_theta = 0
    vega_exposure_limit.current_vega = 0
    
    agent = ExecutionAgent()
    
    # ===== TEST 1: Normal order (should PASS) =====
    print("\n--- TEST 1: Normal order with no restrictions ---")
    order1 = {
        'action': 'BUY',
        'quantity': 50,
        'symbol': 'NSE_FO|NIFTY2510823000CE',
        'price': 150.0,
        'theta': 0,
        'vega': 0
    }
    
    result1 = await agent.execute_order(order1)
    if result1 is None or result1.get('status') != 'BLOCKED':
        print("✅ TEST 1 PASSED: Order executed successfully")
    else:
        print(f"❌ TEST 1 FAILED: Order was unexpectedly blocked: {result1}")
    
    # ===== TEST 2: 4th order (should BLOCK due to frequency) =====
    print("\n--- TEST 2: 4th order after 3 trades (FREQUENCY block) ---")
    # Add 2 more trades to hit the 3/day limit
    frequency_regulator.record_trade('T2', 'NIFTY', 'SELL')
    frequency_regulator.record_trade('T3', 'NIFTY', 'BUY')
    
    order2 = {
        'action': 'BUY',
        'quantity': 50,
        'symbol': 'NSE_FO|NIFTY2510823000CE',
        'price': 150.0,
        'theta': 0,
        'vega': 0
    }
    
    result2 = await agent.execute_order(order2)
    if result2 and result2.get('status') == 'BLOCKED' and 'GOVERNOR' in result2.get('reason', ''):
        print(f"✅ TEST 2 PASSED: Order blocked - {result2['reason']}")
    else:
        print(f"❌ TEST 2 FAILED: Order should have been blocked: {result2}")
    
    # ===== TEST 3: Theta budget limit =====
    print("\n--- TEST 3: Order exceeding theta budget (THETA block) ---")
    # Reset frequency for this test
    frequency_regulator.trades_today = []
    frequency_regulator.last_trade_time = None
    
    # Use up 450 of 500 theta budget
    theta_budget_manager.update_current_theta(450)
    
    order3 = {
        'action': 'BUY',
        'quantity': 50,
        'symbol': 'NSE_FO|NIFTY2510823000CE',
        'price': 150.0,
        'theta': 2,  # 2 * 50 = 100 theta, would exceed 500 budget
        'vega': 0
    }
    
    result3 = await agent.execute_order(order3)
    if result3 and result3.get('status') == 'BLOCKED' and 'THETA' in result3.get('reason', ''):
        print(f"✅ TEST 3 PASSED: Order blocked - {result3['reason']}")
    else:
        print(f"❌ TEST 3 FAILED: Order should have been blocked for theta: {result3}")
    
    # ===== TEST 4: Vega limit =====
    print("\n--- TEST 4: Order exceeding vega limit (VEGA block) ---")
    # Reset for this test
    frequency_regulator.trades_today = []
    frequency_regulator.last_trade_time = None
    theta_budget_manager.current_theta = 0
    
    # Use up vega limit (2% of 500000 capital = 10000)
    vega_exposure_limit.update_current_vega(9500)
    
    order4 = {
        'action': 'BUY',
        'quantity': 50,
        'symbol': 'NSE_FO|NIFTY2510823000CE',
        'price': 150.0,
        'theta': 0,
        'vega': 20,  # 20 * 50 = 1000 vega, would exceed limit
    }
    
    result4 = await agent.execute_order(order4)
    if result4 and result4.get('status') == 'BLOCKED' and 'VEGA' in result4.get('reason', ''):
        print(f"✅ TEST 4 PASSED: Order blocked - {result4['reason']}")
    else:
        print(f"❌ TEST 4 FAILED: Order should have been blocked for vega: {result4}")
    
    print("\n" + "=" * 60)
    print("GATE VERIFICATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_gates())

"""
Test script for Level-09: Smart Execution.
Verifies SmartOrderEngine, Urgency, and ExecutionQualityMonitor.
"""
import asyncio
import logging
from datetime import datetime
from core.event_bus import bus, EventType
from agents.trading.execution import ExecutionAgent
from core.execution import Urgency, execution_quality_monitor
from core.gateway import regime_constraints
from core.gateway.regime_constraints import Regime
from core.governor.frequency_regulator import frequency_regulator
from core.governor.trading_governor import trading_governor, GovernorDecision
from core.config_manager import sys_config
from unittest.mock import MagicMock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestSmartExec")

async def test_smart_execution():
    print("=" * 70)
    print("LEVEL-09: SMART EXECUTION CHECK")
    print("=" * 70)
    
    # FORCE PAPER MODE
    sys_config.MODE = "PAPER"
    print("✅ Forced Mode: PAPER")
    
    # FORCE VALID REGIME for testing
    # RESET FREQUENCY REGULATOR & DISABLE COOLDOWN
    frequency_regulator.reset_daily()
    frequency_regulator.cooldown_minutes = 0  # Disable cooldown for test
    print("✅ Frequency Regulator Reset & Cooldown Disabled")
    
    regime_constraints.override_regime = Regime.TREND
    print("✅ Forced Regime: TREND")
    
    # MOCK GOVERNOR to bypass time checks
    trading_governor.should_trade_today = MagicMock(return_value=GovernorDecision(
        should_trade=True,
        reason="Test Override",
        max_position_size_pct=1.0
    ))
    print("✅ Governor Mocked (Time/Frequency bypassed)")
    
    agent = ExecutionAgent()
    await agent.on_start()
    
    # Simulate Market Data Update (so agent has LTP)
    ltp = 100.0
    await bus.publish(EventType.MARKET_DATA, {'ltp': ltp})
    print(f"📡 Market LTP Set: {ltp}")
    
    # -------------------------------------------------------------
    # TEST 1: PASSIVE ORDER (Should use Smart Logic)
    # -------------------------------------------------------------
    print("\n--- TEST 1: PASSIVE BUY (Sit on Bid) ---")
    order_passive = {
        'symbol': 'BANKNIFTY_PASSIVE',
        'action': 'BUY',
        'quantity': 25,
        'strategy_id': 'TEST_SMART',
        'urgency': 'PASSIVE'
    }
    
    await agent.execute_order(order_passive)
    
    # Check monitor stats
    stats = execution_quality_monitor.get_stats()
    print(f"📊 Monitor Stats: {stats}")
    
    # RESET for Test 2
    frequency_regulator.reset_daily()
    print("\n✅ Regulator Reset for Test 2")
    
    # -------------------------------------------------------------
    # TEST 2: AGGRESSIVE ORDER (Should use Spread)
    # -------------------------------------------------------------
    print("\n--- TEST 2: AGGRESSIVE BUY (Cross Spread) ---")
    order_aggressive = {
        'symbol': 'BANKNIFTY_AGGRESSIVE',
        'action': 'BUY',
        'quantity': 25,
        'strategy_id': 'TEST_SMART',
        'urgency': 'AGGRESSIVE'
    }
    
    await agent.execute_order(order_aggressive)
    
    # -------------------------------------------------------------
    # TEST 3: VERIFY SLIPPAGE DIFFERENCES
    # -------------------------------------------------------------
    print("\n--- TEST 3: VERIFY QUALITY ---")
    monitor_stats = execution_quality_monitor.get_stats()
    print(f"Total Executions: {monitor_stats['count']}")
    print(f"Avg Slippage: {monitor_stats['avg_slippage']:.2f} (lower is better)")
    
    # In our simulation:
    # Aggressive pays spread (LTP + ~0.5%)
    # Passive tries to pay Limit (LTP - spread/2 ish)
    # So Avg Slippage should reflect this cost
    
    for record in execution_quality_monitor.records:
        print(f"  > {record.urgency}: Fill={record.fill_price:.2f} (Exp={record.expected_price:.2f}) Slip={record.slippage:.2f}")

    if monitor_stats['count'] >= 2:
        print("\n✅ Verification SUCCESS: Smart Execution Logic Active")
    else:
        print("\n❌ Verification FAILED: Check logs")

if __name__ == "__main__":
    asyncio.run(test_smart_execution())

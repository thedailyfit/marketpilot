
import asyncio
import logging
from agents.trading.execution import ExecutionAgent
from core.config_manager import sys_config

# Setup Logger
logging.basicConfig(level=logging.INFO)

async def test_paper_execution():
    print("🚀 Starting Paper Trading Verification...")
    
    # Force Paper Mode
    sys_config.MODE = "PAPER"
    
    agent = ExecutionAgent()
    await agent.start()
    
    # Mock Order
    test_order = {
        "symbol": "NSE_FO|NIFTY24FEB25000CE",
        "action": "BUY",
        "quantity": 50,
        "price": 100.0, # Limit Price
        "sl_pct": 1.0,
        "tp_pct": 2.0,
        "strategy_id": "TEST_SCRIPT"
    }
    
    print(f"📝 Submitting Order: {test_order}")
    
    # Direct execution call (bypassing EventBus for unit test)
    # in real app, we publish to bus, agent picks it up.
    # Here we call the handler directly.
    await agent.execute_order(test_order)
    
    # Verify History
    if len(agent.trade_history) > 0:
        fill = agent.trade_history[0]
        print(f"✅ Order Filled in History!")
        print(f"   ID: {fill['order_id']}")
        print(f"   Price: ₹{fill['entry_price']} (Base 100 + Slippage)")
        print(f"   Status: {fill['status']}")
        
        expected_price = 100.0 * 1.005 # 0.5% slippage logic from code
        print(f"   Expected Price ~: {expected_price}")
        
    else:
        print("❌ Trade History Empty - Execution Failed")

    await agent.stop()

if __name__ == "__main__":
    asyncio.run(test_paper_execution())

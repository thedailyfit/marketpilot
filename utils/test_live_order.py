import asyncio
import sys
import logging
sys.path.insert(0, '.')
from core.config_manager import sys_config
from core.event_bus import bus, EventType
from agents.trading.execution import ExecutionAgent
from agents.trading.risk import RiskAgent

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    print("WARNING: This script will place a REAL LIVE MARKET ORDER (1 Quantity).")
    print("Ensure you have funds and are within market hours.")
    confirm = input("Type 'YES' to proceed: ")
    if confirm != "YES":
        print("Aborted.")
        return

    # Force Live Mode
    sys_config.MODE = "LIVE"
    
    # Initialize Agents
    execution_agent = ExecutionAgent()
    risk_agent = RiskAgent() # Risk agent validates the signal
    
    await execution_agent.start()
    await risk_agent.start()
    
    print("Agents Started. Generating Test Signal...")
    
    # Create a Test Signal
    # Note: Using generic symbol. Update to valid Instrument Key if needed.
    test_symbol = "NSE_EQ|INE002A01018" # RELIANCE EQ (Safer than Option)
    # Or use user config symbol if available
    
    signal = {
        "symbol": test_symbol,
        "signal_type": "BUY",
        "quantity": 1,
        "price": 0.0,
        "timestamp": 0.0,
        "reason": "MANUAL_TEST",
        "strategy_id": "TEST_SCRIPT"
    }
    
    print(f"Publishing Signal: {signal}")
    await bus.publish(EventType.SIGNAL, signal)
    
    # Wait for processing
    print("Signal Sent. Waiting for Execution Log...")
    await asyncio.sleep(5)
    
    # Check History
    print("\nTrade History:")
    for trade in execution_agent.trade_history:
        print(trade)
        
    await execution_agent.stop()
    await risk_agent.stop()

if __name__ == "__main__":
    asyncio.run(main())

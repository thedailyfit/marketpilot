import asyncio
import logging
import uvicorn
from core.event_bus import bus, EventType
from core.config_manager import sys_config
from agents.trading.execution import ExecutionAgent
from agents.trading.risk import RiskAgent
from agents.finance.accounting import AccountingAgent

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PaperTest")

async def test_paper_trade():
    logger.info("--- Starting Paper Trade Verification ---")
    
    # Force Config to PAPER
    sys_config.MODE = "PAPER"
    
    # Initialize Agents
    execution_agent = ExecutionAgent()
    risk_agent = RiskAgent()
    accounting_agent = AccountingAgent()
    
    # Start Agents
    await execution_agent.on_start()
    await risk_agent.on_start()
    await accounting_agent.on_start()
    
    # Allow agents to subscribe
    await asyncio.sleep(0.5)
    
    # Mock Market Data (Need LTP for paper fill)
    # ExecutionAgent needs an LTP to fill at.
    await bus.publish(EventType.MARKET_DATA, {
        "symbol": "NSE_FO|NIFTY",
        "ltp": 19550.0,
        "volume": 100,
        "timestamp": 1234567890
    })
    
    logger.info("Injected Tick Data (LTP: 19550.0)")
    await asyncio.sleep(0.1)

    # Create Test Signal
    signal = {
        "symbol": "NSE_FO|NIFTY",
        "signal_type": "BUY",
        "quantity": 50, # 1 Lot
        "price": 0.0,
        "timestamp": 1234567890,
        "reason": "PAPER_TEST_SCRIPT",
        "strategy_id": "TEST_V1"
    }
    
    logger.info(f"Injecting Signal: {signal}")
    await bus.publish(EventType.SIGNAL, signal)
    
    # Wait for processing
    await asyncio.sleep(2.0)
    
    # Verify Results
    logger.info("--- Verification Results ---")
    logger.info(f"Trade History: {execution_agent.trade_history}")
    
    metrics = accounting_agent.get_finance_metrics()
    logger.info(f"Accounting Metrics: {metrics}")
    
    if len(execution_agent.trade_history) > 0:
        last_trade = execution_agent.trade_history[-1]
        if last_trade['mode'] == 'PAPER' and last_trade['status'] == 'FILLED':
             logger.info("✅ SUCCESS: Paper Trade Executed Successfully!")
        else:
             logger.error("❌ FAILURE: Trade executed but status/mode incorrect.")
    else:
        logger.error("❌ FAILURE: No trade recorded.")

    # Cleanup
    await execution_agent.on_stop()

if __name__ == "__main__":
    asyncio.run(test_paper_trade())

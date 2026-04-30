import asyncio
import logging
import sys
import os

# Ensure path is correct
sys.path.append(os.getcwd())

from core.event_bus import bus, EventType
from agents.ops.supervisor import SupervisorAgent
from core.config_manager import sys_config

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SystemCheck")

async def run_diagnostics():
    logger.info("==========================================")
    logger.info("   MARKETPILOT AI - SYSTEM DIAGNOSTIC     ")
    logger.info("==========================================")
    
    # 1. Initialize Supervisor (which inits all other agents)
    supervisor = SupervisorAgent()
    
    # 2. Start Agents
    logger.info("[1/5] Starting Agent Swarm...")
    await supervisor.start()
    
    # 3. Monitor for 10 seconds (Simulate Trading)
    logger.info("[2/5] listening for events (10s)...")
    await asyncio.sleep(10)
    
    # 4. Check Metrics
    logger.info("[3/5] Collecting Metrics...")
    metrics = supervisor.get_system_metrics()
    
    print("\n--- PERFORMANCE REPORT ---")
    print(f"Paper Balance:    ₹{metrics['paper']['balance']:.2f}")
    print(f"Realized P&L:     ₹{metrics['paper']['realized_pnl']:.2f}")
    print(f"Unrealized P&L:   ₹{metrics['paper']['unrealized_pnl']:.2f}")
    print("--------------------------\n")
    
    # 5. Check Log Files
    logger.info("[4/5] Verifying Persistence...")
    has_history = os.path.exists("data/history") and len(os.listdir("data/history")) > 0
    has_logs = os.path.exists("data/logs/trade_log.csv")
    
    if has_history: logger.info("✅ TICK HISTORY: Confirmed")
    else: logger.error("❌ TICK HISTORY: Missing")
    
    if has_logs: logger.info("✅ TRADE LOGS: Confirmed")
    else: logger.warning("⚠️ TRADE LOGS: No trades executed yet (checking permission/logic)")

    # 6. Shutdown
    logger.info("[5/5] Shutting Down...")
    await supervisor.stop()
    logger.info("DIAGNOSTIC COMPLETE.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_diagnostics())

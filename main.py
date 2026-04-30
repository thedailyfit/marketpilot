import asyncio
import logging
from agents.market_data import MarketDataAgent
from agents.strategy import StrategyAgent
from agents.execution import ExecutionAgent
from config import TRADING_SYMBOL

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Main")

def get_user_selection():
    print("\n" + "="*40)
    print("   AI TRADER SETUP WIZARD   ")
    print("="*40)
    
    print("\n1. Select Index:")
    print("   [1] NIFTY 50")
    print("   [2] BANK NIFTY")
    index_choice = input("   Enter Choice (1/2): ")
    symbol_root = "NIFTY" if index_choice == "1" else "BANKNIFTY"
    
    expiry = input("\n2. Enter Expiry (e.g., 26OCT23): ").upper().strip()
    strike = input("\n3. Enter Strike Price (e.g., 19500): ").strip()
    
    print("\n4. Select Option Type:")
    print("   [1] CE (Call)")
    print("   [2] PE (Put)")
    type_choice = input("   Enter Choice (1/2): ")
    opt_type = "CE" if type_choice == "1" else "PE"
    
    # Construct Symbol (Format might vary based on broker, standardizing for NSE FO)
    # Standard format often: NIFTY23OCT19500CE
    # Note: User must verify this format matches their broker's exact symbol master
    final_symbol = f"NSE_FO|{symbol_root}{expiry}{strike}{opt_type}"
    
    print(f"\n✅ TRADING CONFIGURATION SET:")
    print(f"   Symbol: {final_symbol}")
    confirm = input("   Start AI Agent with this? (y/n): ")
    if confirm.lower() != 'y':
        print("Exiting...")
        exit()
        
    return final_symbol

async def main():
    # interactive setup
    selected_symbol = get_user_selection()
    
    # Update global config for this session (Monkey Patch)
    import config
    config.TRADING_SYMBOL = selected_symbol
    
    logger.info(f"Initializing Multi-Agent Trading System for {config.TRADING_SYMBOL}...")
    
    # 1. Create Queues for communication (The "Nerves" of the system)
    market_data_queue = asyncio.Queue()
    execution_order_queue = asyncio.Queue()
    
    # 2. Instantiate Agents
    market_agent = MarketDataAgent(output_queue=market_data_queue)
    execution_agent = ExecutionAgent(input_queue=execution_order_queue)
    strategy_agent = StrategyAgent(
        input_queue=market_data_queue,
        execution_queue=execution_order_queue
    )
    
    # 3. Start Agents
    await execution_agent.initialize()
    await execution_agent.start()
    await strategy_agent.start()
    await market_agent.start()
    
    logger.info("System is Live! Press Ctrl+C to stop.")
    
    # Keep the main loop alive
    try:
        while True:
            # Monitor system health or print stats here
            await asyncio.sleep(5)
            logger.info("Heartbeat: System healthy...")
    except asyncio.CancelledError:
        logger.info("System shutting down...")
        await market_agent.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

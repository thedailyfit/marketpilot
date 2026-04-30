
import asyncio
import logging
import sys
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Diagnostic")

print("🔍 Starting Diagnostic Check...")

try:
    print("1. Importing new_server...")
    import new_server
    print("✅ new_server imported.")
except Exception as e:
    print(f"❌ Failed to import new_server: {e}")
    sys.exit(1)

async def test_startup():
    print("2. Testing Supervisor Initialization...")
    try:
        from agents.ops.supervisor import supervisor
        print("   Found supervisor instance.")
        
        # Check if agents are initialized
        agents = [
            "market_data_agent",
            "strategy_agent",
            "risk_agent", 
            "execution_agent", 
            "deep_scan_agent",
            "monitor_agent", 
            "oi_decoder"
        ]
        
        for agent_name in agents:
            if hasattr(supervisor, agent_name):
                agent = getattr(supervisor, agent_name)
                print(f"   - {agent_name}: {'INITIALIZED' if agent else 'NONE'}")
            else:
                print(f"   - {agent_name}: MISSING")
                
        print("3. Attempting Mock Startup Loop...")
        # supervisor.start() calls start() on all agents.
        # We will manually start them to trace which one hangs.
        
        print(f"   Agents to start: {len(supervisor.agents)}")
        for i, agent in enumerate(supervisor.agents):
            name = getattr(agent, 'name', f'Agent_{i}')
            print(f"   ▶️ Starting [{i+1}/{len(supervisor.agents)}] {name}...", end='', flush=True)
            try:
                # Use asyncio.wait_for to catch hangs
                await asyncio.wait_for(agent.start(), timeout=5.0)
                print(f" ✅ DONE")
            except asyncio.TimeoutError:
                print(f" ❌ TIMEOUT! (Agent hung)")
                print(f"   CRITICAL: {name} is blocking the event loop!")
                break
            except Exception as e:
                 print(f" ❌ ERROR: {e}")
        
        print("✅ Diagnostic Complete (Startup Phase).")
        
    except Exception as e:
        print(f"❌ Supervisor Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_startup())

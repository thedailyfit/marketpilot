"""
Test Real Upstox Connection
Explicity tests the WebSocket connection to Upstox API using the token in .env.
Bypasses market hours check to force connection attempt.
"""
import sys
import asyncio
import logging
from datetime import datetime

# Setup path
sys.path.insert(0, '.')

from core.upstox_stream import UpstoxWebSocket, Tick
from core.config_manager import sys_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_connection():
    print("\n" + "="*60)
    print("  🔗 UPSTOX REAL CONNECTION TEST")
    print("="*60)
    
    # Check token
    token = sys_config.ACCESS_TOKEN
    masked_token = f"{token[:10]}...{token[-10:]}" if token else "None"
    print(f"  Access Token: {masked_token}")
    
    if not token:
        print("  ❌ No Access Token found in .env! Aborting.")
        return

    # Create instance
    stream = UpstoxWebSocket()
    
    # Monkeypatch market hours check to force connection
    print("  🔧 Bypassing market hours check...")
    stream._check_market_hours = lambda: True
    
    # Add callbacks
    async def on_tick(tick: Tick):
        print(f"  ⚡ TICK: {tick.symbol} ₹{tick.ltp} (Change: {tick.change_percent}%)")
        
    stream.on_tick = on_tick
    
    # Connect
    print("  ⏳ Connecting to Upstox WebSocket...")
    asyncio.create_task(stream.connect())
    
    # Wait for connection
    for _ in range(10):
        if stream.is_connected:
            print("  ✅ WebSocket Connected!")
            break
        await asyncio.sleep(1)
        
    if not stream.is_connected:
        print("  ❌ Failed to connect after 10 seconds.")
        print("     Check if Token is valid or expired.")
        return
        
    # Subscribe to test symbol
    test_symbol = "NSE_INDEX|Nifty 50"
    print(f"  📡 Subscribing to {test_symbol}...")
    await stream.subscribe(test_symbol, mode="full")
    
    # Listen for a few seconds
    print("  👂 Listening for data (10s)...")
    await asyncio.sleep(10)
    
    # Close
    print("  🛑 Closing connection...")
    await stream.close()
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        asyncio.run(test_connection())
    except KeyboardInterrupt:
        print("Stopped by user")

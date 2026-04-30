
import asyncio
import aiohttp
import json

async def test_backend():
    print("--- 1. Testing API Endpoints ---")
    async with aiohttp.ClientSession() as session:
        endpoints = [
            "/api/settings",
            "/api/system-status",
            "/api/intelligence"
        ]
        
        for ep in endpoints:
            try:
                async with session.get(f"http://127.0.0.1:8000{ep}", timeout=2) as resp:
                    print(f"GET {ep}: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"   > Response keys: {list(data.keys())}")
            except Exception as e:
                print(f"GET {ep} FAILED: {e}")

    print("\n--- 2. Testing WebSocket Stream ---")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect('ws://127.0.0.1:8000/ws/stream') as ws:
                print("WebSocket Connected!")
                
                # Wait for 3 seconds for messages
                start = asyncio.get_event_loop().time()
                count = 0
                while asyncio.get_event_loop().time() - start < 5:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            print(f"   > Received: {data['type']}")
                            if data['type'] == 'TICK':
                                print(f"     -> Symbol: {data['data'].get('symbol')} LTP: {data['data'].get('ltp')}")
                                count += 1
                                if count > 2: break
                    except asyncio.TimeoutError:
                        pass
                
                print(f"Total Ticks Received: {count}")
    except Exception as e:
        print(f"WebSocket FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_backend())

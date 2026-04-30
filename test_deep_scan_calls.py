
import asyncio
from agents.analytics.deep_scan import DeepScanAgent

async def test_ai_calls():
    print("🧬 Testing Deep Scan AI Calls...")
    agent = DeepScanAgent()
    # Mock current LTP for consistent results
    agent.last_ltp = 25000 
    
    report = await agent.perform_deep_scan("NSE_FO|NIFTY")
    
    if "ai_calls" in report:
        print("✅ AI Calls Generated:")
        for call in report['ai_calls']:
            print(f"   - {call['type']}: {call['contract']}")
    else:
        print("❌ AI Calls Missing from Report")

if __name__ == "__main__":
    asyncio.run(test_ai_calls())

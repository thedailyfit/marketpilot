import asyncio
from agents.analytics.deep_scan import DeepScanAgent

async def test():
    print("Initializing Agent...")
    agent = DeepScanAgent()
    print("Running Scan...")
    try:
        res = await agent.perform_deep_scan("NSE_FO|NIFTY")
        print("Scan Result:", res)
    except Exception as e:
        print("CRASH DETECTED:")
        import traceback
        traceback.print_exc()

    
    # Test Volume
    print("Testing Volume Agent...")
    try:
        from agents.analytics.volume import VolumeFlowAgent
        vol = VolumeFlowAgent()
        p = vol.get_volume_profile()
        print("Volume Profile:", p)
    except Exception as e:
        print("VOLUME CRASH:", e)
        import traceback
        traceback.print_exc()

    # Test Prediction
    print("Testing Prediction Engine...")
    try:
        from agents.analytics.prediction import PredictionEngine
        pred = PredictionEngine()
        res = pred.predict_success("TestStrat", "NSE_FO|NIFTY_19500_CE")
        print("Prediction Result:", res)
    except Exception as e:
        print("PREDICTION CRASH:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())

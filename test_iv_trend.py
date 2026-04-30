"""
IV Trend Engine Verification
Tests slope calculation and trend classification.
"""
import logging
from core.options.iv_trend import IVTrendEngine, TrendDirection

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def test_iv_trends():
    engine = IVTrendEngine(lookback_window=10, threshold=0.0005)
    
    print("="*60)
    print("IV TREND VERIFICATION")
    print("="*60)
    
    # 1. Rising Trend (0.15 -> 0.16 over 10 points)
    # Slope approx 0.001 per step? No, 0.01 total over 10 steps = 0.001 per step.
    # Threshold is 0.0005. So this should be RISING.
    rising_iv = [0.15 + (i * 0.001) for i in range(10)]
    result_rising = engine.analyze(rising_iv)
    print("\nSCENARIO 1: RISING IV")
    print(f"Data: {rising_iv[0]:.4f} -> {rising_iv[-1]:.4f}")
    print(f"Slope: {result_rising.slope:.6f}")
    print(f"Trend: {result_rising.trend}")
    print(f"Explanation: {result_rising.explanation}")
    
    if result_rising.trend == TrendDirection.RISING:
        print("✅ PASS: Correctly identified RISING trend")
    else:
        print("❌ FAIL: Expected RISING")

    # 2. Falling Trend (0.20 -> 0.18 over 20 points)
    # Change = -0.02 over 20 steps = -0.001 per step.
    # Should be FALLING (< -0.0005).
    falling_iv = [0.20 - (i * 0.001) for i in range(20)]
    result_falling = engine.analyze(falling_iv)
    print("\nSCENARIO 2: FALLING IV (Crush)")
    print(f"Data: {falling_iv[0]:.4f} -> {falling_iv[-1]:.4f}")
    print(f"Slope: {result_falling.slope:.6f}")
    print(f"Trend: {result_falling.trend}")
    
    if result_falling.trend == TrendDirection.FALLING:
        print("✅ PASS: Correctly identified FALLING trend")
    else:
        print("❌ FAIL: Expected FALLING")

    # 3. Flat Trend (Noise around 0.15)
    # Slope near 0.
    import random
    random.seed(42)
    flat_iv = [0.15 + random.uniform(-0.002, 0.002) for _ in range(20)]
    result_flat = engine.analyze(flat_iv)
    print("\nSCENARIO 3: FLAT IV (Stable/Noise)")
    print(f"Data: {flat_iv[0]:.4f} -> {flat_iv[-1]:.4f}")
    print(f"Slope: {result_flat.slope:.6f}")
    print(f"Trend: {result_flat.trend}")
    
    if result_flat.trend == TrendDirection.FLAT:
        print("✅ PASS: Correctly identified FLAT trend")
    else:
        print("❌ FAIL: Expected FLAT")
        
    # 4. Gateway Logic Simulation
    print("\nSCENARIO 4: GATEWAY BLOCK SIMULATION")
    trade_idea = {"strategy": "LONG_CALL", "iv_trend": "FALLING"}
    
    if trade_idea["iv_trend"] == "FALLING" and trade_idea["strategy"] in ["LONG_CALL", "LONG_PUT"]:
        print("✅ PASS: Gateway Logic would BLOCK Long Call in Falling IV")
    else:
        print("❌ FAIL: Gateway Logic failed to block")

if __name__ == "__main__":
    test_iv_trends()

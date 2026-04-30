import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_deep_scan():
    print("\n[1] Testing Deep Scan (/analyze/deep)...")
    try:
        start = time.time()
        response = requests.post(f"{BASE_URL}/analyze/deep")
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Deep Scan Success ({elapsed:.2f}s)")
            print(f"   Status: {data.get('status')}")
            print(f"   Regime: {data.get('macro_scan', {}).get('market_regime')}")
            print(f"   Score: {data.get('macro_scan', {}).get('consensus_score')}")
            print(f"   Rec: {data.get('macro_scan', {}).get('recommendation')}")
            return True
        else:
            print(f"❌ Deep Scan Failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Deep Scan Error: {e}")
        return False

def test_paper_trade():
    print("\n[2] Testing Paper Execution (/execute)...")
    symbol = "NSE_FO|NIFTY23500CE"
    try:
        params = {
            "symbol": symbol,
            "action": "BUY",
            "quantity": 50,
            "product": "MIS"
        }
        response = requests.post(f"{BASE_URL}/execute", params=params)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Trade Execution Success")
            print(f"   Order ID: {data.get('order_id')}")
            print(f"   Status: {data.get('status')}")
            return True
        else:
            print(f"❌ Execution Failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Execution Error: {e}")
        return False

def test_order_history():
    print("\n[3] Verifying Order History (/api/trades)...")
    try:
        response = requests.get(f"{BASE_URL}/api/trades")
        
        if response.status_code == 200:
            orders = response.json()
            print(f"✅ History Fetch Success")
            print(f"   Total Orders: {len(orders)}")
            if len(orders) > 0:
                last_order = orders[-1]
                print(f"   Last Order: {last_order.get('action')} {last_order.get('symbol')} @ {last_order.get('entry_price')}")
            return True
        else:
            print(f"❌ History Fetch Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ History Error: {e}")
        return False

def start_system():
    print("\n[0] Starting AI System (/start)...")
    try:
        requests.post(f"{BASE_URL}/start")
        print("✅ Start Signal Sent")
        time.sleep(2) # Wait for startup
    except Exception as e:
        print(f"❌ Start Failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting Dashboard Backend Verification")
    start_system()
    if test_deep_scan():
        time.sleep(1)
        if test_paper_trade():
            time.sleep(1)
            test_order_history()

import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def check_server_up():
    try:
        requests.get(f"{BASE_URL}/docs", timeout=2)
        print("✅ Server is reachable.")
        return True
    except:
        print("❌ Server is DOWN or unreachable.")
        return False

def check_agents():
    print("\n🔍 Checking Agent Status...")
    try:
        # Depending on available endpoints. Using a known one or new_server's root.
        # new_server.py has /api/system-status
        res = requests.get(f"{BASE_URL}/api/system-status")
        if res.status_code == 200:
            data = res.json()
            active = data.get("active_agents", 0)
            status = data.get("status", "Unknown")
            print(f"✅ System Status: {status} | Active Agents: {active}")
            
            if active < 5:
                print("⚠️ Warning: Low agent count. Expected > 20.")
            
            trinity = data.get("trinity_status", {})
            print(f"   - Whale Radar: {trinity.get('whale_radar')}")
            print(f"   - Sentiment: {trinity.get('sentiment_score')}")
            return True
        else:
            print(f"❌ Failed to get system status. Code: {res.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking agents: {e}")
        return False

def test_deep_scan():
    print("\n🔍 Testing Deep Scan analysis...")
    try:
        # Assuming system is started
        requests.post(f"{BASE_URL}/start") # Ensure started
        
        # This endpoint was fixed in previous turn
        res = requests.post(f"{BASE_URL}/analyze/deep")
        data = res.json()
        if data.get("status") == "Success":
            rec = data['macro_scan'].get('recommendation', 'N/A')
            print(f"✅ Deep Scan Successful. Rec: {rec}")
        else:
            print(f"❌ Deep Scan Failed: {data}")
    except Exception as e:
        print(f"❌ Deep Scan Error: {e}")

def test_optimizer():
    print("\n🔍 Testing Turbo Optimizer...")
    try:
        # 1. Trigger
        res = requests.post(f"{BASE_URL}/api/optimize")
        if res.status_code != 200:
            print(f"❌ Failed to trigger optimizer: {res.text}")
            return

        print("   - Optimization triggered. Polling for results...")
        
        # 2. Poll
        for i in range(15):
            time.sleep(1)
            res = requests.get(f"{BASE_URL}/api/optimize/results")
            data = res.json()
            
            is_opt = data.get("is_optimizing")
            best = data.get("best_config")
            gens = data.get("generations")
            
            sys.stdout.write(f"\r   - Poll {i+1}: Optimizing={is_opt}, Gens={gens}, Best={best is not None}   ")
            sys.stdout.flush()
            
            if not is_opt and best:
                print(f"\n✅ Optimization Completed! Best Config: {best}")
                return
        
        print("\n⚠️ Optimization timed out or did not finish in expected time.")
        
    except Exception as e:
        print(f"\n❌ Optimizer Error: {e}")

if __name__ == "__main__":
    if check_server_up():
        check_agents()
        test_deep_scan()
        test_optimizer()

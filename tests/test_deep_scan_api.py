import requests
import json
import time

API_URL = "http://127.0.0.1:8000"

def test_deep_scan():
    print(f"Activating System at {API_URL}/start...")
    try:
        requests.post(f"{API_URL}/start")
        time.sleep(2) # Wait for startup
    except:
        print("Start failed")

    print(f"Testing Deep Scan API at {API_URL}/analyze/deep...")
    try:
        response = requests.post(f"{API_URL}/analyze/deep")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Deep Scan Response:")
            print(json.dumps(data, indent=2))
            
            if data.get("status") == "Success":
                 print("\n✅ SUCCESS: Deep Scan returned valid data.")
            else:
                 print("\n❌ FAILURE: Deep Scan returned error status.")
        else:
            print(f"\n❌ HTTP Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"\n❌ Connection Error: {e}")

if __name__ == "__main__":
    test_deep_scan()

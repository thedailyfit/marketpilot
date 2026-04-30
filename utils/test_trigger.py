import requests
import time

API = "http://127.0.0.1:8000"

def run():
    print("1. Triggering /start...")
    try:
        r = requests.post(f"{API}/start")
        print(f"Response: {r.json()}")
    except Exception as e:
        print(f"Error: {e}")

    print("2. System Started. Waiting for ticks...")
    time.sleep(5)
    print("Done.")

if __name__ == "__main__":
    run()

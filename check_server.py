
import requests
import sys

url = "http://127.0.0.1:8000/dashboard/ai_command.html"
try:
    print(f"Testing URL: {url}")
    response = requests.get(url, timeout=5)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("✅ Server is accessible!")
    else:
        print("❌ Server returned error code.")
except Exception as e:
    print(f"❌ Connection Failed: {e}")

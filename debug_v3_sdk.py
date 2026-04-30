
import os
import sys
import logging
import threading
from dotenv import load_dotenv
import upstox_client
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3

# Config Logging
logging.basicConfig(level=logging.DEBUG)

# Load Env
load_dotenv()
API_KEY = os.getenv("API_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

print(f"API_KEY: {API_KEY}")
print(f"ACCESS_TOKEN: {ACCESS_TOKEN[:10]}... (Length: {len(ACCESS_TOKEN)})")

def on_open():
    print(">>> OPEN: Connected to Upstox V3")
    # Subscribe
    instrument_keys = ["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank"]
    print(f">>> SUBSCRIBING TO: {instrument_keys}")
    streamer.subscribe(instrument_keys, "full")

def on_close():
    print(">>> CLOSE: Connection Closed")

def on_error(error):
    print(f">>> ERROR: {error}")

def on_message(data):
    print(f">>> DATA RECEIVED: {data}")

# Setup Streamer
try:
    config = upstox_client.Configuration()
    config.access_token = ACCESS_TOKEN
    api_client = upstox_client.ApiClient(config)
    
    streamer = MarketDataStreamerV3(api_client, [], "full")
    streamer.on("open", on_open)
    streamer.on("close", on_close)
    streamer.on("error", on_error)
    streamer.on("message", on_message)
    
    print(">>> CONNECTING...")
    streamer.connect()
    
except Exception as e:
    print(f"EXCEPTION: {e}")

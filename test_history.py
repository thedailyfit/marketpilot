
import upstox_client
from dotenv import load_dotenv
import os
import datetime

load_dotenv()
access_token = os.getenv("ACCESS_TOKEN")

if not access_token:
    print("No Token")
    exit()

configuration = upstox_client.Configuration()
configuration.access_token = access_token
api_client = upstox_client.ApiClient(configuration)
history_api = upstox_client.HistoryApi(api_client)

instrument_key = "NSE_INDEX|Nifty 50"
interval = "1minute"
to_date = datetime.datetime.now().strftime("%Y-%m-%d")
from_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

print(f"Fetching history for {instrument_key} from {from_date} to {to_date}")

try:
    # get_historical_candle_data(instrument_key, interval, to_date, from_date, api_version='2.0') 
    # Valid intervals: 1minute, 30minute, day, etc.
    # Note: Upstox API arg order might be instrument_key, interval, to_date, from_date
    response = history_api.get_historical_candle_data_v1(instrument_key, interval, to_date, from_date)
    print("Status:", response.status)
    if response.data and response.data.candles:
        print(f"Candles received: {len(response.data.candles)}")
        print("Sample:", response.data.candles[0])
    else:
        print("No candles found")
except Exception as e:
    print(f"Error: {e}")
    # Try alternate method name if v1 fails (sometimes it's just get_historical_candle_data)
    try:
        print("Retrying with get_historical_candle_data...")
        resp = history_api.get_historical_candle_data(instrument_key, interval, to_date, from_date)
        print("Success V3:", resp)
    except Exception as e2:
        print(f"Error 2: {e2}")

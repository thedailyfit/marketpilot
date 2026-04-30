
try:
    from upstox_client.feeder.market_data_feed import MarketDataFeed
    print("SUCCESS: from upstox_client.feeder.market_data_feed import MarketDataFeed")
except ImportError as e:
    print(f"FAILED: {e}")

try:
    from upstox_client.websocket.market_data_feed import MarketDataFeed
    print("SUCCESS: from upstox_client.websocket.market_data_feed import MarketDataFeed")
except ImportError as e:
    print(f"FAILED: {e}")

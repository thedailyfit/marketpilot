
try:
    import upstox_client
    print(f"Upstox Client Path: {upstox_client.__file__}")
    print("Top level dir:", dir(upstox_client))
    
    # Try common streamer locations
    try:
        from upstox_client.feeder.market_data_feed import MarketDataFeed
        print("Found MarketDataFeed")
    except ImportError:
        print("MarketDataFeed not found in feeder.market_data_feed")

    try:
        from upstox_client.websocket.market_data.market_data_feed import MarketDataFeed
        print("Found websocket.market_data.MarketDataFeed")
    except ImportError:
        pass

except Exception as e:
    print(e)

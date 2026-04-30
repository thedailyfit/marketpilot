"""
Test Upstox Official SDK with Sandbox Mode
"""
import os
from dotenv import load_dotenv

# Load credentials
load_dotenv()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
API_KEY = os.getenv("API_KEY")

print("=" * 60)
print("  🧪 UPSTOX SANDBOX SDK TEST")
print("=" * 60)
print(f"  API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
print(f"  Token: {ACCESS_TOKEN[:20]}...{ACCESS_TOKEN[-10:]}")

# Test 1: API Configuration with Sandbox
try:
    import upstox_client
    from upstox_client.rest import ApiException
    
    # Configure with sandbox mode
    configuration = upstox_client.Configuration()
    configuration.access_token = ACCESS_TOKEN
    # configuration.sandbox = True  # Disabled - sandbox APIs limited
    
    print("\n✅ SDK Configuration Created (Production Mode with Sandbox Token)")
    
    # Test 2: Get User Profile
    api_instance = upstox_client.UserApi(upstox_client.ApiClient(configuration))
    
    try:
        user_profile = api_instance.get_profile("2.0")
        print(f"\n✅ User Profile Retrieved:")
        print(f"   Client ID: {user_profile.data.client_id}")
        print(f"   Email: {user_profile.data.email}")
        print(f"   User Type: {user_profile.data.user_type}")
    except ApiException as e:
        print(f"\n⚠️ Profile API Error: {e.status} - {e.reason}")
        
    # Test 3: Get Market Data Feed Authorization (for WebSocket)
    ws_api = upstox_client.WebsocketApi(upstox_client.ApiClient(configuration))
    
    try:
        ws_auth = ws_api.get_market_data_feed_authorize("2.0")
        print(f"\n✅ WebSocket Authorization Successful!")
        print(f"   WS URL: {ws_auth.data.authorized_redirect_uri[:50]}...")
    except ApiException as e:
        print(f"\n⚠️ WebSocket Auth Error: {e.status} - {e.reason}")
        if e.status == 401:
            print("   → Token may be invalid or sandbox not enabled for this endpoint")
        elif e.status == 410:
            print("   → Resource gone - try during market hours or check subscription")
            
    # Test 4: Get Market Quote (simpler test)
    market_api = upstox_client.MarketQuoteApi(upstox_client.ApiClient(configuration))
    
    try:
        quote = market_api.get_full_market_quote("NSE_INDEX|Nifty 50", "2.0")
        print(f"\n✅ Market Quote Retrieved:")
        print(f"   Symbol: Nifty 50")
        print(f"   LTP: ₹{quote.data.get('NSE_INDEX:Nifty 50', {}).get('last_price', 'N/A')}")
    except ApiException as e:
        print(f"\n⚠️ Market Quote Error: {e.status} - {e.reason}")

except ImportError as e:
    print(f"\n❌ Import Error: {e}")
except Exception as e:
    print(f"\n❌ Unexpected Error: {e}")

print("\n" + "=" * 60)
print("  Test Complete")
print("=" * 60)

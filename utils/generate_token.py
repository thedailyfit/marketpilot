from __future__ import print_function
import upstox_client
from upstox_client.rest import ApiException
from config import API_KEY, API_SECRET, REDIRECT_URI
import webbrowser

def generate_token():
    print(f"1. Please visit this URL to login: https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={API_KEY}&redirect_uri={REDIRECT_URI}")
    
    # Try to open automatically
    try:
        webbrowser.open(f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={API_KEY}&redirect_uri={REDIRECT_URI}")
    except:
        pass

    auth_code = input("\n2. After login, you will be redirected to a URL (localhost). \n   Copy the 'code' parameter from that URL and paste it here: ")

    api_version = '2.0'
    api_instance = upstox_client.LoginApi()

    try:
        # Get token API
        api_response = api_instance.token(api_version, code=auth_code, client_id=API_KEY, client_secret=API_SECRET, redirect_uri=REDIRECT_URI, grant_type='authorization_code')
        print(f"\nSUCCESS! Access Token:\n{api_response.access_token}")
        print("\nPlease update your .env file with this token.")
        
    except ApiException as e:
        print("Exception when calling LoginApi->token: %s\n" % e)

if __name__ == "__main__":
    generate_token()

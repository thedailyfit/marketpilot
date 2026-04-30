import os
from dotenv import load_dotenv

load_dotenv()

# Upstox Credentials
API_KEY = os.getenv("UPSTOX_API_KEY")
API_SECRET = os.getenv("UPSTOX_API_SECRET")
REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:5000/callback")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

# Trading Configuration
TRADING_SYMBOL = "NSE_FO|NIFTY23OCT19500CE" # Example: Nifty CE Strike
QUANTITY = 50 # 1 Lot Nifty
TIMEFRAME = "1minute" 

# Scalping Risk Management Rules
STOP_LOSS_PCT = 0.02   # 2% Max Stop Loss (Tighter for Real execution test)
TAKE_PROFIT_PCT = 0.02 # 2% Profit Target (Quick Scalp)
TRAILING_SL_Start_PCT = 0.015 # Start trailing early

# Risk Management
MAX_LOSS_PER_DAY = 2000 # Hard Limit
MAX_POSITIONS = 1 # One trade at a time

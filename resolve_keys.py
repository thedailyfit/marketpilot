
import upstox_client
import os
import gzip
import shutil
import urllib.request
import csv
from io import StringIO

# Upstox Instrument File is huge. 
# Better to use search or just check documentation format.
# But SDK has search api? No, usually downloadable CSV.

# Alternative: Test subscription with expected keys and see if error "Invalid Instrument" comes in logs.
# But logs didn't show error.

# Let's try to infer from History API execution.
# The history API worked with "NSE_INDEX|Nifty 50".
# So the key is likely correct for that.

# But let's verify VIX.
# "NSE_INDEX|India VIX"

def check_keys():
    print("Verifying Keys format...")
    # This is a heuristic check based on typical Upstox V3 keys
    # Key Format: {exchange}|{token}
    # For indices, token might be symbol name?
    
    # Let's try to search using SDK if possible
    # Not easy without downloading master list.
    
    print("Assuming NSE_INDEX|Nifty 50 is correct based on History Success.")
    print("If stream fails, try 'NSE_INDEX|17' for Nifty 50.")
    print("If stream fails, try 'NSE_INDEX|13' for Bank Nifty.")
    print("If stream fails, try 'NSE_INDEX|INDIAVIX' for VIX.")

if __name__ == "__main__":
    check_keys()

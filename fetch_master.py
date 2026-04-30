
import requests
import gzip
import shutil
import csv
import io

def fetch_and_search():
    # URL found in search results for NSE Exchange instruments
    url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz"
    print(f"Downloading {url}...")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        print("Download complete. Decompressing...")
        with gzip.open(io.BytesIO(response.content), 'rt') as f:
            reader = csv.DictReader(f)
            
            print("Searching for Indices...")
            found_nifty = False
            found_bank = False
            found_vix = False
            
            for row in reader:
                name = row.get('name', '')
                tradingsymbol = row.get('tradingsymbol', '')
                instrument_key = row.get('instrument_key', '')
                
                # Nifty 50
                if 'Nifty 50' in name or 'Nifty 50' in tradingsymbol:
                    print(f"FOUND NIFTY 50: {name} | {tradingsymbol} | KEY: {instrument_key}")
                    found_nifty = True
                    
                # Bank Nifty
                if 'Nifty Bank' in name or 'Nifty Bank' in tradingsymbol:
                    print(f"FOUND BANK NIFTY: {name} | {tradingsymbol} | KEY: {instrument_key}")
                    found_bank = True
                    
                # VIX
                if 'VIX' in name or 'VIX' in tradingsymbol:
                     print(f"FOUND VIX: {name} | {tradingsymbol} | KEY: {instrument_key}")
                     found_vix = True
            
            if not found_nifty: print("Nifty 50 NOT FOUND in NSE_INDEX.csv")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_and_search()

import sqlite3
import os
import time

DB_PATH = "data/market_data.db"

def verify():
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Count Ticks
        cursor.execute("SELECT count(*) FROM market_ticks")
        count_ticks = cursor.fetchone()[0]
        
        # Count Greeks
        cursor.execute("SELECT count(*) FROM option_greeks")
        count_greeks = cursor.fetchone()[0]
        
        print(f"✅ Data Mine Verification:")
        print(f"   - Ticks Recorded: {count_ticks}")
        print(f"   - Greeks Recorded: {count_greeks}")
        
        if count_ticks > 0:
            print("   INFO: System is successfully recording data!")
        else:
            print("   WARNING: No data yet. Wait for simulation.")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading DB: {e}")

if __name__ == "__main__":
    verify()

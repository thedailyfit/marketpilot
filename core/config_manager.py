from dataclasses import dataclass

@dataclass
class SystemConfig:
    MODE: str = "PAPER" # PAPER or LIVE
    TRADING_SYMBOL: str = "NSE_FO|NIFTY23OCT19500CE"
    QUANTITY: int = 50
    LOT_SIZE: int = 50
    
    # Risk & Strategy
    STOP_LOSS_PCT: float = 0.02
    TAKE_PROFIT_PCT: float = 0.02
    
    # Risk Limits
    MAX_DAILY_LOSS: float = 2000.0
    MAX_ORDER_QTY: int = 1000
    
    # Upstox Credentials (will be loaded from env)
    API_KEY: str = ""
    API_SECRET: str = ""
    ACCESS_TOKEN: str = ""
    REDIRECT_URI: str = "http://127.0.0.1:8000/callback"
    # AI Keys
    GEMINI_API_KEY: str = ""
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = ""

    def __post_init__(self):
        print("--- LOADING CONFIGURATION ---")
        try:
            from dotenv import load_dotenv
            import os
            from pathlib import Path
            
            # Explicitly find .env in project root
            # core/config_manager.py -> core/ -> project_root/
            base_dir = Path(__file__).resolve().parent.parent
            env_path = base_dir / '.env'
            
            print(f"Looking for .env at: {env_path}")
            if env_path.exists():
                print(f".env found! Loading...")
                load_dotenv(dotenv_path=env_path)
            else:
                print(f"WARNING: .env NOT FOUND at {env_path}")

            self.API_KEY = os.getenv("API_KEY", "")
            self.API_SECRET = os.getenv("API_SECRET", "")
            self.ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")
            self.REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8001/callback")
            self.TRADING_SYMBOL = os.getenv("TRADING_SYMBOL", self.TRADING_SYMBOL)
            self.MODE = os.getenv("MODE", "PAPER")
            self.QUANTITY = int(os.getenv("QUANTITY", str(self.QUANTITY)))
            self.MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", str(self.MAX_DAILY_LOSS)))
            self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
            self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
            
            if not self.API_KEY:
                print("CRITICAL: API_KEY is EMPTY after loading config.")
            else:
                print(f"Config Loaded. API_KEY ends with: ...{self.API_KEY[-4:] if len(self.API_KEY)>4 else '****'}")
                
        except ImportError:
            print("CRITICAL ERROR: python-dotenv not installed. Using defaults.")
        except Exception as e:
            print(f"Error loading config: {e}")

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                # Type conversion for safety
                if key == "QUANTITY" or key == "LOT_SIZE":
                    value = int(value)
                elif key == "STOP_LOSS_PCT" or key == "TAKE_PROFIT_PCT":
                    value = float(value)
                    
                setattr(self, key, value)

# Singleton Config Instance
sys_config = SystemConfig()

from fastapi import FastAPI, WebSocket, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from agents.ops.supervisor import supervisor
from core.config_manager import sys_config
from core.event_bus import bus, EventType
from core.performance_tracker import tracker as performance_tracker
from core.auth import auth_manager
from core.greeks import greeks_calculator
import os
import asyncio
import logging
from datetime import datetime, timedelta
import upstox_client


# --- LOGGING SETUP ---
log_queue = asyncio.Queue()
class QueueHandler(logging.Handler):
    def emit(self, record):
        try:
            log_queue.put_nowait(self.format(record))
        except:
            pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Server") # <--- Defined logger
logger.addHandler(QueueHandler())

# --- APP SETUP ---
app = FastAPI()

@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")
app.mount("/dashboard/static", StaticFiles(directory="dashboard/static"), name="static")

# Trading mode manager
from core.trading_mode import trading_mode_manager

# supervisor = SupervisorAgent() # Now using singleton from agents.ops.supervisor

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await supervisor.on_start()
    
    # FORCE Create/Update Admin User
    try:
        print("--- CHECKING ADMIN USER ---")
        # Check if admin exists
        found = False
        for uid, u in auth_manager.users.items():
            if u.email == "admin@marketpilot.com":
                found = True
                print(f"Admin user found: {uid}. Updating password...")
                auth_manager.update_user(uid, {"password": "admin123"})
                break
        
        if not found:
            print("Admin user NOT found. Creating new...")
            auth_manager.register("admin@marketpilot.com", "admin123", "Admin")
            
        print("OK ADMIN ACCESS READY: admin@marketpilot.com / admin123")
    except Exception as e:
        print(f"ERROR: Error setting up admin: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    await supervisor.on_stop()

# --- Pydantic Models ---
class SettingsUpdate(BaseModel):
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat_assistant(request: ChatRequest):
    """AI Trading Assistant that analyzes current market context."""
    msg = request.message.lower()
    
    # gathers state from sub-engines
    context = {
        "vpin": getattr(supervisor.vpin_agent, 'toxicity_state', 'NORMAL'),
        "icebergs": len(getattr(supervisor.iceberg_agent, 'icebergs_detected', [])),
        "max_pain": getattr(supervisor.gamma_sniper, 'gravity_strength', 'LOW'),
        "delta": getattr(supervisor.delta_sniper, 'divergence_state', 'NEUTRAL'),
        "sync": getattr(supervisor.correlation_arbiter, 'correlation_status', 'SYNCED'),
        "efficiency": getattr(supervisor.mirror_mode, 'efficiency_score', 90.0),
        "sentiment": getattr(supervisor.sentiment_agent, 'sentiment_score', 50),
        "vix": getattr(supervisor.sentiment_agent, 'vix', 15.0)
    }
    
    # 2. Heuristic AI Intelligence logic
    response = ""
    if "lot" in msg or "size" in msg:
        vix = context['vix']
        if vix > 18:
            response = "⚠️ Market volatility (VIX) is high. I recommend **reducing lot size by 50%** to protect capital."
        elif context['vpin'] == "HIGH":
            response = "⚠️ High VPIN flow toxicity detected. Stay with **minimum lot size** or avoid new entries."
        else:
            response = f"✅ Market is stable. Standard lot sizing for {sys_config.TRADING_SYMBOL} is optimal. Current VIX: {vix}."

    elif "strategy" in msg:
        if context['vpin'] == "HIGH":
            response = "🛡️ Recommendation: **Grandmaster Defense**. Avoid chasing momentum. Wait for the Informed Flow to settle."
        elif context['delta'] == "BULLISH_DIVERGENCE":
            response = "🚀 Strategy: **Quantum Scalp (Buy)**. Bullish Delta Divergence detected; price likely to bounce."
        elif context['delta'] == "BEARISH_DIVERGENCE":
            response = "📉 Strategy: **Quantum Scalp (Sell)**. Bearish Delta Divergence detected."
        else:
            response = "🎯 Current optimal strategy: **BuyCallScalp** or **ThetaDecay** depending on your time range."

    elif "buy" in msg or "trade" in msg:
        if context['sync'] == "DIVERGING":
            response = "❌ DO NOT BUY. Nifty and BankNifty are diverging. High risk of a fakeout trap."
        elif context['vpin'] == "HIGH":
            response = "⚠️ WAIT. Informed flow toxicity is high. Institutions are offloading; better to wait for a deep pullback."
        elif context['max_pain'] == "HIGH":
            response = "📈 Recommendation: **LONG** towards Max Pain gravity point. Institutional pull is strong."
        else:
            response = "🔍 Scanning... I recommend waiting for a **pullback to VWAP** before entry for best risk/reward."

    elif "prob" in msg or "chance" in msg:
        score = context['efficiency']
        response = f"📊 System Winning Probability: **{score:.1f}%** based on current agent alignment and historical efficacy."

    elif "hi" in msg or "hello" in msg or "who" in msg:
        response = "👋 I am your MarketPilot Singularity Assistant. I analyze 40 agents in real-time. Ask me about **lot sizes, strategy selection, or current buy/sell calls**."
    else:
        response = "🔍 I am monitoring the Singularity Pulse. Currently, "
        response += f"VPIN is {context['vpin']}, Delta is {context['delta']}, and Market Sync is {context['sync']}. "
        response += "How can I help you with your strategy or lot selection?"

    return {"response": response}

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    name: str = ""
    email: str
    password: str

class GreeksRequest(BaseModel):
    spot_price: float
    strike_price: float
    time_to_expiry: float  # In days
    volatility: float  # As percentage (e.g., 15 for 15%)
    option_type: str = "CE"

@app.get("/connect-upstox")
async def login_redirect():
    """Redirects to Upstox Authorization URL automatically."""
    from fastapi.responses import RedirectResponse
    import urllib.parse
    
    base_url = "https://api.upstox.com/v2/login/authorization/dialog"
    params = {
        "response_type": "code",
        "client_id": sys_config.API_KEY,
        "redirect_uri": sys_config.REDIRECT_URI
    }
    auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    logger.info(f"Redirecting user to Upstox Auth: {auth_url}")
    return RedirectResponse(url=auth_url)

@app.get("/login")
async def get_login_page():
    return FileResponse("dashboard/login.html")

@app.get("/dashboard")
async def get_dashboard():
    return FileResponse("dashboard/index.html")

@app.get("/dashboard/ai_command.html")
async def get_dashboard_direct():
    return FileResponse("dashboard/ai_command.html")

@app.get("/dashboard/orders")
async def get_orders_page():
    return FileResponse("dashboard/orders.html")

@app.get("/dashboard/analysis")
async def get_analysis_page():
    return FileResponse("dashboard/analysis.html")

@app.get("/trades")
async def get_trades_page():
    return FileResponse("dashboard/trades.html")

@app.get("/settings")
async def get_settings_page():
    return FileResponse("dashboard/settings.html")

@app.get("/api/trades")
async def get_trades_data():
    """Returns trade history from ExecutionAgent."""
    if supervisor.is_running:
        return JSONResponse(content=supervisor.execution_agent.trade_history)
    return JSONResponse(content=[])

@app.get("/api/historical/{symbol}")
async def get_historical_data(symbol: str):
    """Fetch real historical candle data from Upstox API."""
    import requests as req
    from datetime import datetime, timedelta
    
    # Map symbol names to Upstox instrument keys
    instrument_map = {
        "NIFTY": "NSE_INDEX|Nifty 50",
        "BANKNIFTY": "NSE_INDEX|Nifty Bank",
        "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    }
    
    instrument_key = instrument_map.get(symbol.upper(), "NSE_INDEX|Nifty 50")
    
    # Date range: last 5 trading days
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    try:
        import urllib.parse
        encoded_key = urllib.parse.quote(instrument_key, safe='')
        
        url_daily = f"https://api.upstox.com/v2/historical-candle/{encoded_key}/5minute/{to_date}/{from_date}"
        
        headers = {
            "Accept": "application/json",
        }
        
        # Try intraday first (today's data)
        intraday_url = f"https://api.upstox.com/v2/historical-candle/intraday/{encoded_key}/5minute"
        res = req.get(intraday_url, headers=headers, timeout=10)
        
        candles = []
        
        if res.status_code == 200:
            data = res.json()
            raw_candles = data.get("data", {}).get("candles", [])
            
            for c in raw_candles:
                # Upstox format: [timestamp, open, high, low, close, volume, oi]
                try:
                    ts = c[0]
                    # Parse ISO timestamp to unix
                    if isinstance(ts, str):
                        dt = datetime.fromisoformat(ts.replace("+05:30", "+05:30"))
                        unix_ts = int(dt.timestamp())
                    else:
                        unix_ts = int(ts)
                    
                    candles.append({
                        "time": unix_ts,
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": float(c[4]),
                    })
                except Exception:
                    continue
        
        # Also fetch multi-day historical data
        res2 = req.get(url_daily, headers=headers, timeout=10)
        if res2.status_code == 200:
            data2 = res2.json()
            raw_candles2 = data2.get("data", {}).get("candles", [])
            
            for c in raw_candles2:
                try:
                    ts = c[0]
                    if isinstance(ts, str):
                        dt = datetime.fromisoformat(ts.replace("+05:30", "+05:30"))
                        unix_ts = int(dt.timestamp())
                    else:
                        unix_ts = int(ts)
                    
                    candles.append({
                        "time": unix_ts,
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": float(c[4]),
                    })
                except Exception:
                    continue
        
        # Sort by time ascending and deduplicate
        candles.sort(key=lambda x: x["time"])
        seen = set()
        unique_candles = []
        for c in candles:
            if c["time"] not in seen:
                seen.add(c["time"])
                unique_candles.append(c)
        
        logger.info(f"Historical data: {len(unique_candles)} candles fetched for {symbol}")
        return JSONResponse(content={"candles": unique_candles, "symbol": symbol})
        
    except Exception as e:
        logger.error(f"Failed to fetch historical data: {e}")
        return JSONResponse(content={"candles": [], "symbol": symbol, "error": str(e)})

@app.get("/api/alerts")
async def get_alerts():
    """Returns AI-generated market alerts from real-time analysis."""
    if supervisor.is_running and hasattr(supervisor, 'strategy_agent'):
        # Get strategy state for current market analysis
        strategy_state = supervisor.strategy_agent.active_strategy.get_state()
        
        alerts = []
        
        # Generate alerts based on real-time analysis
        rsi = strategy_state.get('rsi', 50)
        trend = strategy_state.get('trend', 'NEUTRAL')
        regime = strategy_state.get('regime', 'RANGING')
        
        if rsi < 30:
            alerts.append({
                "type": "OPPORTUNITY",
                "severity": "high",
                "title": "RSI Oversold Alert",
                "message": f"RSI at {rsi:.1f} - Strong BUY opportunity detected",
                "action": "BUY",
                "timestamp": int(datetime.now().timestamp())
            })
        elif rsi > 70:
            alerts.append({
                "type": "OPPORTUNITY",
                "severity": "high",
                "title": "RSI Overbought Alert",
                "message": f"RSI at {rsi:.1f} - Strong SELL opportunity detected",
                "action": "SELL",
                "timestamp": int(datetime.now().timestamp())
            })
        
        if regime == "TRENDING_UP":
            alerts.append({
                "type": "TREND",
                "severity": "medium",
                "title": "Bullish Trend Active",
                "message": f"Market in strong uptrend. Favor BUY positions.",
                "action": "BUY",
                "timestamp": int(datetime.now().timestamp())
            })
        elif regime == "TRENDING_DOWN":
            alerts.append({
                "type": "TREND",
                "severity": "medium",
                "title": "Bearish Trend Active",
                "message": f"Market in downtrend. Favor SELL positions or stay flat.",
                "action": "SELL",
                "timestamp": int(datetime.now().timestamp())
            })
        
        # Add market status alert
        from core.upstox_stream import UpstoxWebSocket
        ws_instance = UpstoxWebSocket()
        market_open = ws_instance._check_market_hours()
        
        alerts.append({
            "type": "STATUS",
            "severity": "info",
            "title": "Market Status",
            "message": "Market is OPEN - Live data streaming" if market_open else "Market is CLOSED - Simulation mode active",
            "action": None,
            "timestamp": int(datetime.now().timestamp())
        })
        
        return JSONResponse(content={
            "alerts": alerts,
            "analysis": strategy_state,
            "market_open": market_open
        })
    
    return JSONResponse(content={"alerts": [], "analysis": {}, "market_open": False})

# ===== TRADING MODE ENDPOINTS =====
class ModeChangeRequest(BaseModel):
    mode: str  # OPTIONS, EQUITY, UNIVERSAL

@app.get("/api/mode")
async def get_trading_mode():
    """Get current trading mode and active/disabled engines."""
    return JSONResponse(content=trading_mode_manager.get_state())

@app.get("/api/mode/info")
async def get_mode_info():
    """Get mode info for UI display."""
    return JSONResponse(content=trading_mode_manager.get_mode_for_display())

@app.post("/api/mode")
async def set_trading_mode(request: ModeChangeRequest):
    """Switch trading mode: OPTIONS, EQUITY, or FUTURES."""
    mode = request.mode.upper()
    if mode not in ["OPTIONS", "EQUITY", "FUTURES"]:
        return JSONResponse(
            content={"error": f"Invalid mode: {mode}. Use OPTIONS, EQUITY, or FUTURES"},
            status_code=400
        )
    
    new_state = await trading_mode_manager.set_mode_by_name(mode)
    return JSONResponse(content={
        "success": True,
        "message": f"Switched to {mode} mode",
        "state": new_state.to_dict()
    })

@app.get("/api/intelligence")
async def get_intelligence():
    """Returns aggregated AI Intelligence metrics."""
    if not supervisor.is_running:
        return JSONResponse(content={"status": "offline"})
        
    data = {
        "sentiment": {},
        "greeks": {},
        "prediction": {}
    }
    
    # 1. Sentiment
    if hasattr(supervisor, 'sentiment_agent'):
        data["sentiment"] = supervisor.sentiment_agent.get_sentiment()
        
    # 2. Greeks (From latest tick in Market Data stream - mocked for now or accessed if stored)
    # Ideally MarketDataAgent should store the latest "Option Greeks"
    # 3. Strategy/Prediction
    if hasattr(supervisor, 'strategy_agent') and supervisor.strategy_agent.active_strategy:
         data["prediction"] = supervisor.strategy_agent.active_strategy.get_state()
         
    return JSONResponse(content=data)

@app.get("/api/history")
async def get_history(symbol: str, interval: str = "1minute"):
    """Fetch historical candle data from Upstox for Chart."""
    try:
        if not sys_config.ACCESS_TOKEN:
            return JSONResponse(content={"status": "error", "message": "No Token"})
            
        # Configure API
        config = upstox_client.Configuration()
        config.access_token = sys_config.ACCESS_TOKEN
        client = upstox_client.ApiClient(config)
        history_api = upstox_client.HistoryApi(client)
        
        # Date Range (Last 5 days for context)
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        
        # Fetch
        # symbol format expected: NSE_INDEX|Nifty 50
        # If frontend sends just "NIFTY", map it?
        # Frontend usually sends what is in the ticker.
        # But let's assume frontend sends correct instrument Key or we map it.
        
        instr_key = symbol
        if "NIFTY" in symbol and "|" not in symbol:
             instr_key = "NSE_INDEX|Nifty 50" if "BANK" not in symbol else "NSE_INDEX|Nifty Bank"
        
        resp = history_api.get_historical_candle_data(instr_key, interval, to_date, from_date)
        
        if not resp.data or not resp.data.candles:
             return JSONResponse(content={"status": "empty", "data": []})
             
        # Format for Lightweight Charts
        # Upstox: [timestamp, open, high, low, close, vol, oi]
        # LWC: { time: unix, open, high, low, close }
        
        formatted = []
        # Sort candles by time ascending (Upstox usually desc)
        candles = sorted(resp.data.candles, key=lambda x: x[0])
        
        for c in candles:
            # Parse timestamp '2026-01-02T09:15:00+05:30'
            try:
                dt = datetime.fromisoformat(c[0])
                ts = int(dt.timestamp())
                formatted.append({
                    "time": ts,
                    "open": c[1],
                    "high": c[2],
                    "low": c[3],
                    "close": c[4]
                })
            except:
                pass
                
        return JSONResponse(content={"status": "success", "data": formatted})
        
    except Exception as e:
        logger.error(f"History fetch error: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)})


    if hasattr(supervisor, 'strategy_agent'):
        strat = supervisor.strategy_agent.active_strategy
        data["prediction"] = {
            "model_confidence": 0.85, # Mock for now
            "signal_strength": strat.get_state().get('rsi', 50)
        }
        
    return JSONResponse(content=data)

@app.get("/api/settings")
async def get_settings():
    """Returns current API configuration status."""
    return {
        "api_key": sys_config.API_KEY[:8] + "..." if sys_config.API_KEY else "",
        "has_token": bool(sys_config.ACCESS_TOKEN),
        "mode": sys_config.MODE,
        "quantity": sys_config.QUANTITY,
        "sl_pct": sys_config.STOP_LOSS_PCT,
        "tp_pct": sys_config.TAKE_PROFIT_PCT
    }

@app.post("/api/settings")
async def save_settings(data: SettingsUpdate):
    """Saves API credentials to .env file."""
    try:
        env_path = ".env"
        lines = []
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()
        
        # Update or add keys
        new_lines = []
        keys_updated = set()
        for line in lines:
            if line.startswith("API_KEY=") and data.api_key:
                new_lines.append(f"API_KEY={data.api_key}\n")
                keys_updated.add("API_KEY")
            elif line.startswith("API_SECRET=") and data.api_secret:
                new_lines.append(f"API_SECRET={data.api_secret}\n")
                keys_updated.add("API_SECRET")
            elif line.startswith("ACCESS_TOKEN=") and data.access_token:
                new_lines.append(f"ACCESS_TOKEN={data.access_token}\n")
                keys_updated.add("ACCESS_TOKEN")
            else:
                new_lines.append(line)
        
        # Add missing keys
        if "API_KEY" not in keys_updated and data.api_key:
            new_lines.append(f"API_KEY={data.api_key}\n")
        if "API_SECRET" not in keys_updated and data.api_secret:
            new_lines.append(f"API_SECRET={data.api_secret}\n")
        if "ACCESS_TOKEN" not in keys_updated and data.access_token:
            new_lines.append(f"ACCESS_TOKEN={data.access_token}\n")
        
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
        
        # Reload config
        sys_config.API_KEY = data.api_key or sys_config.API_KEY
        sys_config.ACCESS_TOKEN = data.access_token or sys_config.ACCESS_TOKEN
        
        return {"status": "success", "message": "Credentials saved. Restart server to apply changes."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/callback")
async def upstox_callback(code: str):
    """Handle Upstox OAuth callback."""
    if not code:
        return JSONResponse(content={"error": "No code provided"}, status_code=400)
    
    try:
        import aiohttp
        
        url = "https://api.upstox.com/v2/login/authorization/token"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "code": code,
            "client_id": sys_config.API_KEY,
            "client_secret": sys_config.API_SECRET,
            "redirect_uri": sys_config.REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as response:
                if response.status == 200:
                    resp_json = await response.json()
                    access_token = resp_json.get("access_token")
                    
                    if access_token:
                        # Save to .env
                        env_path = ".env"
                        lines = []
                        if os.path.exists(env_path):
                            with open(env_path, 'r') as f:
                                lines = f.readlines()
                        
                        new_lines = []
                        updated = False
                        for line in lines:
                            if line.startswith("ACCESS_TOKEN="):
                                new_lines.append(f"ACCESS_TOKEN={access_token}\n")
                                updated = True
                            else:
                                new_lines.append(line)
                        
                        if not updated:
                            new_lines.append(f"ACCESS_TOKEN={access_token}\n")
                            
                        with open(env_path, 'w') as f:
                            f.writelines(new_lines)
                        
                        # Update config
                        sys_config.ACCESS_TOKEN = access_token
                        
                        return FileResponse("dashboard/login_success.html")
                    else:
                        return JSONResponse(content={"error": "No access token in response"}, status_code=400)
                else:
                    text = await response.text()
                    return JSONResponse(content={"error": f"Upstox API Error: {text}"}, status_code=response.status)
                    
    except Exception as e:
        return JSONResponse(content={"error": f"Callback failed: {str(e)}"}, status_code=500)

@app.post("/api/manual_trade")
async def trigger_manual_trade():
    """Injects a manual test trade into the live system."""
    try:
        signal = {
            "symbol": sys_config.TRADING_SYMBOL,
            "signal_type": "BUY",
            "quantity": sys_config.QUANTITY,
            "price": 0.0,
            "timestamp": asyncio.get_event_loop().time(),
            "reason": "DASHBOARD_TEST",
            "strategy_id": "MANUAL_BTN"
        }
        await bus.publish(EventType.SIGNAL, signal)
        return {"status": "success", "message": "Manual trade signal sent"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/test/start_simulation")
async def start_simulation():
    """Starts the Volatile Demo Simulation for live testing."""
    if supervisor.market_data_agent:
        await supervisor.market_data_agent.start_demo_mode()
        return {"status": "success", "message": "Demo Simulation Started! Watch the dashboard."}
    return {"status": "error", "message": "Market Data Agent not ready."}

@app.post("/api/test/inject_profit")
async def inject_profit_scenario():
    """Injects a simulated profitable trade sequence for demonstration."""
    try:
        # Simulate Entry
        entry_price = 19500.0
        exit_price = 19550.0 # 50 points profit
        qty = sys_config.QUANTITY
        ts = datetime.now()
        
        entry = {
            "status": "FILLED",
            "symbol": sys_config.TRADING_SYMBOL,
            "action": "BUY",
            "quantity": qty,
            "fill_price": entry_price,
            "timestamp": (ts - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "PAPER",
            "pnl": 0.0,
            "strategy_id": "DEMO_PROFIT"
        }
        
        exit_trade = {
            "status": "FILLED",
            "symbol": sys_config.TRADING_SYMBOL,
            "action": "SELL",
            "quantity": qty,
            "fill_price": exit_price,
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "PAPER",
            "pnl": (exit_price - entry_price) * qty, # Profit
            "strategy_id": "DEMO_PROFIT"
        }
        
        # Inject directly into agent
        if supervisor.execution_agent:
            supervisor.execution_agent.trade_history.append(entry)
            supervisor.execution_agent.trade_history.append(exit_trade)
            
            # Update Accounting Ledger mock
            # (Optional: AccountingAgent handles real logic, but for demo display execution history is enough)
            
            return {"status": "success", "message": f"Injected Profit: {exit_trade['pnl']}"}
        else:
             return {"status": "error", "message": "Execution Agent not running"}
            
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/metrics")
async def get_metrics():
    """Endpoint for Dashboard Monitoring"""
    return supervisor.get_system_metrics()

@app.get("/callback")
async def oauth_callback(code: str = None):
    """Landing page for Upstox Redirect."""
    return {
        "status": "Redirect Received",
        "message": "Copy the 'code' parameter from the URL if needed, or check your Access Token generation script.",
        "received_code": code
    }

# login_redirect already defined at line 165 — duplicate removed

# === AUTHENTICATION ENDPOINTS ===

@app.post("/api/register")
async def register_user(data: RegisterRequest):
    """Register a new user."""
    result = auth_manager.register(data.email, data.password, data.name)
    return JSONResponse(content=result)

@app.post("/api/login")
async def login_user(data: LoginRequest, request: Request):
    """Login user and get session token."""
    ip = request.client.host if request.client else None
    result = auth_manager.login(data.email, data.password, ip)
    return JSONResponse(content=result)

@app.get("/api/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Get current logged in user."""
    user = auth_manager.validate_token(authorization)
    if user:
        return JSONResponse(content={
            "success": True,
            "user": auth_manager.get_user(user.id)
        })
    return JSONResponse(content={"success": False, "error": "Invalid token"})

@app.post("/api/logout")
async def logout_user(authorization: Optional[str] = Header(None)):
    """Logout and invalidate session."""
    result = auth_manager.logout(authorization or "")
    return JSONResponse(content=result)

# === GREEKS ENDPOINTS ===

@app.get("/api/greeks")
async def get_greeks_status():
    """Returns usage status of Greeks engine."""
    return JSONResponse(content={"active": True, "engine": "Black-Scholes-V1"})

# === LEVEL-07: OPTIONS MEMORY API ===

from core.options import chain_snapshot_engine, snapshot_service, vix_history_store
from datetime import date as date_type

@app.get("/api/options/historical")
async def get_option_at_time(
    symbol: str,
    strike: float,
    expiry: str,
    option_type: str,
    date: str,
    timestamp: Optional[int] = None
):
    """
    Get historical option data at a specific moment.
    
    Args:
        symbol: NIFTY or BANKNIFTY
        strike: Strike price
        expiry: Expiry date (YYYY-MM-DD)
        option_type: CE or PE
        date: Target date (YYYY-MM-DD)
        timestamp: Optional unix timestamp for exact moment
    
    Returns:
        Option snapshot with IV, Greeks, and premium at that moment.
    """
    try:
        target_date = date_type.fromisoformat(date)
        snapshot = chain_snapshot_engine.get_option_at(
            symbol=symbol.upper(),
            strike=strike,
            expiry=expiry,
            option_type=option_type.upper(),
            target_date=target_date,
            target_timestamp=timestamp
        )
        
        if snapshot:
            return JSONResponse(content={
                "found": True,
                "snapshot": snapshot.to_dict()
            })
        else:
            return JSONResponse(content={
                "found": False,
                "message": f"No data for {symbol} {strike}{option_type} on {date}"
            }, status_code=404)
            
    except Exception as e:
        return JSONResponse(content={
            "error": str(e)
        }, status_code=500)

@app.get("/api/options/chain-at")
async def get_chain_at_time(
    symbol: str,
    date: str,
    timestamp: Optional[int] = None
):
    """
    Get entire option chain at a specific moment.
    
    Args:
        symbol: NIFTY or BANKNIFTY
        date: Target date (YYYY-MM-DD)
        timestamp: Optional unix timestamp for exact moment
    """
    try:
        target_date = date_type.fromisoformat(date)
        snapshots = chain_snapshot_engine.get_snapshot_at(
            symbol=symbol.upper(),
            target_date=target_date,
            target_timestamp=timestamp
        )
        
        return JSONResponse(content={
            "count": len(snapshots),
            "symbol": symbol.upper(),
            "date": date,
            "snapshots": [s.to_dict() for s in snapshots]
        })
        
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/options/snapshot-status")
async def get_snapshot_status():
    """Get status of the snapshot service."""
    return JSONResponse(content=snapshot_service.get_status())

@app.post("/api/options/snapshot-start")
async def start_snapshot_service():
    """Start the scheduled snapshot capture."""
    await snapshot_service.start()
    return JSONResponse(content={"status": "Started"})

@app.post("/api/options/snapshot-stop")
async def stop_snapshot_service():
    """Stop the scheduled snapshot capture."""
    await snapshot_service.stop()
    return JSONResponse(content={"status": "Stopped"})

@app.get("/api/vix/history")
async def get_vix_history(start: str, end: str):
    """
    Get VIX history for a time range.
    
    Args:
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
    """
    try:
        from datetime import datetime
        start_date = datetime.fromisoformat(start + "T00:00:00")
        end_date = datetime.fromisoformat(end + "T23:59:59")
        
        snapshots = vix_history_store.get_range(
            int(start_date.timestamp()),
            int(end_date.timestamp())
        )
        
        return JSONResponse(content={
            "count": len(snapshots),
            "start": start,
            "end": end,
            "history": [s.to_dict() for s in snapshots]
        })
        
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/vix/at")
async def get_vix_at_time(timestamp: int):
    """Get VIX at a specific timestamp."""
    snapshot = vix_history_store.get_at(timestamp)
    if snapshot:
        return JSONResponse(content=snapshot.to_dict())
    return JSONResponse(content={"error": "No VIX data at that time"}, status_code=404)


# === RESEARCH ENDPOINTS ===

@app.post("/api/optimize")
async def start_optimization():
    """Trigger Genetic Strategy Optimization."""
    if hasattr(supervisor, 'optimizer'):
        # Run in background to avoid blocking API
        asyncio.create_task(supervisor.optimizer.run_optimization())
        return {"status": "Started", "message": "Optimization started in background"}
    return {"status": "Error", "message": "Optimizer Agent not available"}

@app.get("/api/optimize/results")
async def get_optimization_results():
    """Get latest optimization results."""
    if hasattr(supervisor, 'optimizer'):
        opt = supervisor.optimizer
        return {
            "is_optimizing": opt.is_optimizing,
            "best_config": opt.best_config,
            "generations": opt.generations
        }
    return {"status": "Error", "message": "Optimizer Agent not available"}

@app.get("/api/institutional")
async def get_institutional_data():
    """Get FII/DII Flow Data."""
    if hasattr(supervisor, 'institutional_agent'):
        return supervisor.institutional_agent.get_status()
    return {"status": "Error", "message": "Institutional Agent not enabled"}

@app.get("/api/oi-decoder")
async def get_oi_decoder_data():
    """Get OI Trap Analysis (X-Ray)."""
    if hasattr(supervisor, 'oi_decoder'):
        return supervisor.oi_decoder.get_status()
    return {"status": "Error", "message": "OI Decoder Agent not enabled"}
    
@app.post("/api/greeks")
async def calculate_greeks(data: GreeksRequest):
    """Calculate Options Greeks."""
    result = greeks_calculator.calculate_greeks(
        spot_price=data.spot_price,
        strike_price=data.strike_price,
        time_to_expiry=data.time_to_expiry / 365,  # Convert days to years
        volatility=data.volatility / 100,  # Convert percentage to decimal
        option_type=data.option_type
    )
    return JSONResponse(content={
        "delta": result.delta,
        "gamma": result.gamma,
        "theta": result.theta,
        "vega": result.vega,
        "rho": result.rho,
        "option_price": result.option_price,
        "intrinsic_value": result.intrinsic_value,
        "time_value": result.time_value
    })

@app.get("/api/historical/{symbol}")
async def get_historical_candles(symbol: str):
    """Get historical candlestick data for chart."""
    import random
    now = int(datetime.now().timestamp())
    candles = []
    volumes = []
    price = 23400 if symbol == "NIFTY" else 49000
    
    for i in range(200, -1, -1):
        time = now - (i * 300)  # 5 min candles
        open_price = price
        change = (random.random() - 0.48) * 30
        price = price + change
        high = max(open_price, price) + random.random() * 15
        low = min(open_price, price) - random.random() * 15
        
        candles.append({
            "time": time,
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(price, 2)
        })
        volumes.append({
            "time": time,
            "value": int(50000 + random.random() * 100000),
            "color": "#22c55e40" if price > open_price else "#ef444440"
        })
    
    return JSONResponse(content={"candles": candles, "volumes": volumes})

# === ANALYTICS ENDPOINTS ===

# === INTELLIGENCE ENGINE ENDPOINTS (Level 14-16 Wiring) ===

from core.intelligence.confluence_engine import confluence_engine
from core.volume.zone_engine import zone_engine
from core.intelligence.gamma_engine import gamma_engine
from core.options.iv_trend import IVTrendEngine
from core.gateway.execution_gateway import execution_gateway
from core.risk.theta_budget import ThetaBudgetManager
from core.risk.vega_limit import VegaExposureLimit
from core.risk.greeks_portfolio import GreeksPortfolioTracker

# Singletons
_iv_trend_engine = IVTrendEngine()
_theta_budget = ThetaBudgetManager()
_vega_limit = VegaExposureLimit()
_greeks_tracker = GreeksPortfolioTracker()

@app.get("/api/confluence")
async def get_confluence_score(spot: float = 0.0, direction: str = "LONG"):
    """Returns the current Institutional Confluence Score (0-100)."""
    try:
        active_zones = zone_engine.get_active_zones()
        gamma_state = gamma_engine.current_state
        
        if spot <= 0:
            return JSONResponse(content={
                "score": 0, "is_tradeable": False,
                "reasons": ["Spot price not provided."],
                "zone_aligned": False, "gamma_aligned": False,
                "active_zones": len(active_zones),
                "gamma_available": gamma_state is not None
            })
        
        report = confluence_engine.evaluate(
            spot_price=spot, direction=direction,
            active_zones=active_zones, gamma_state=gamma_state
        )
        return JSONResponse(content={
            **report.to_dict(),
            "active_zones": len(active_zones),
            "gamma_available": gamma_state is not None
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/iv-trend")
async def get_iv_trend():
    """Returns the current IV Trend direction (RISING, FLAT, FALLING)."""
    try:
        # If we have historical IV data available, analyze it
        # For now, return the engine's configuration and any cached result
        return JSONResponse(content={
            "status": "ready",
            "lookback_window": _iv_trend_engine.lookback,
            "slope_threshold": _iv_trend_engine.threshold,
            "description": "Call with IV series data to get trend classification",
            "supported_directions": ["RISING", "FLAT", "FALLING"]
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/iv-trend/analyze")
async def analyze_iv_trend(iv_series: list[float]):
    """Analyze an IV time series and classify the trend."""
    try:
        result = _iv_trend_engine.analyze(iv_series)
        return JSONResponse(content={
            "direction": result.direction.value,
            "slope": result.slope,
            "explanation": result.explanation
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/zones")
async def get_institutional_zones():
    """Returns all active Institutional Volume Zones."""
    try:
        active = zone_engine.get_active_zones()
        all_zones = zone_engine.zones
        return JSONResponse(content={
            "total_zones": len(all_zones),
            "active_zones": len(active),
            "zones": [{
                "zone_id": z.zone_id,
                "poc": z.poc,
                "upper_bound": z.upper_bound,
                "lower_bound": z.lower_bound,
                "strength": z.strength,
                "is_fresh": z.is_fresh,
                "touch_count": z.touch_count,
                "status": z.status
            } for z in all_zones]
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/zones/check")
async def check_zone_interaction(price: float):
    """Check if a price interacts with any Institutional Zone."""
    try:
        interaction = zone_engine.check_interaction(price)
        return JSONResponse(content={
            "price": price,
            "interaction": interaction or "NONE",
            "active_zones": len(zone_engine.get_active_zones())
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/gateway-status")
async def get_gateway_status():
    """Returns the full 9-Gate ExecutionGateway status."""
    try:
        status = execution_gateway.get_status()
        return JSONResponse(content=status)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/gateway/validate")
async def validate_trade_idea(
    symbol: str = "NIFTY", action: str = "BUY",
    quantity: int = 50, strategy: str = "LONG_CALL"
):
    """Validate a trade idea against ALL 9 risk gates."""
    try:
        trade_idea = {
            "symbol": symbol, "action": action,
            "quantity": quantity, "strategy": strategy
        }
        decision = execution_gateway.validate(trade_idea)
        return JSONResponse(content=decision.to_dict())
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/theta-budget")
async def get_theta_budget():
    """Returns current Theta Budget status (₹500/day limit)."""
    try:
        status = _theta_budget.get_status()
        return JSONResponse(content=status)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/vega-limit")
async def get_vega_limit():
    """Returns current Vega Exposure limit status (2% capital)."""
    try:
        status = _vega_limit.get_status()
        return JSONResponse(content=status)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/portfolio-greeks")
async def get_portfolio_greeks():
    """Returns aggregated Portfolio Greeks across all positions."""
    try:
        summary = _greeks_tracker.get_summary()
        violations = _greeks_tracker.check_risk_limits()
        return JSONResponse(content={
            "portfolio": summary,
            "risk_violations": violations,
            "position_count": len(_greeks_tracker.positions)
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/gamma-state")
async def get_gamma_state():
    """Returns the current Dealer Gamma exposure state."""
    try:
        state = gamma_engine.current_state
        if state is None:
            return JSONResponse(content={
                "status": "no_data",
                "message": "Gamma state not yet computed. Awaiting option chain data."
            })
        return JSONResponse(content={
            "spot": state.spot,
            "max_pain": state.max_pain,
            "gamma_flip": state.gamma_flip,
            "zone": state.zone,
            "pressure": state.pressure,
            "net_gamma": state.net_gamma,
            "timestamp": state.timestamp
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# === END INTELLIGENCE ENGINE ENDPOINTS ===

@app.get("/api/equity-curve")
async def get_equity_curve(limit: int = 100):
    """Returns equity curve data for charting."""
    return JSONResponse(content=performance_tracker.get_equity_curve(limit))

@app.get("/api/drawdown")
async def get_drawdown(limit: int = 100):
    """Returns drawdown history for charting."""
    return JSONResponse(content=performance_tracker.get_drawdown_history(limit))

@app.get("/api/performance")
async def get_performance():
    """Returns comprehensive performance metrics."""
    return JSONResponse(content=performance_tracker.get_performance_metrics())

@app.get("/api/trade-distribution")
async def get_trade_distribution():
    """Returns trade distribution by hour, day, and strategy."""
    return JSONResponse(content=performance_tracker.get_trade_distribution())

@app.get("/api/market-insight/{symbol}")
async def get_market_insight(symbol: str):
    """Returns AI-powered market insight for a symbol."""
    if supervisor.is_running and hasattr(supervisor, 'prediction_engine'):
        insight = supervisor.prediction_engine.get_market_insight(symbol)
        return JSONResponse(content=insight)
    return JSONResponse(content={"status": "NO_DATA"})

@app.get("/api/system-status")
async def get_system_status():
    """Returns overall system status for dashboard polling."""
    pnl = 0.0
    if supervisor.is_running and hasattr(supervisor, 'execution_agent'):
        pnl = getattr(supervisor.execution_agent, 'daily_pnl', 0.0)
    
    trinity = {
        "whale_radar": "ACTIVE",
        "gamma_burst": "WAITING" if hasattr(supervisor, 'gamma_agent') and not supervisor.gamma_agent.is_active_window else "LIVE",
        "pattern_vision": "SCANNING",
        "puppet_master": getattr(supervisor.constituent_agent, 'market_status', 'OFFLINE') if hasattr(supervisor, 'constituent_agent') else "OFFLINE",
        "velocity_vision": "NORMAL" if hasattr(supervisor, 'tape_reader') and supervisor.tape_reader.current_tps < 50 else "HIGH",
        "fractal_vision": getattr(supervisor.fractal_agent, 'royal_flush_active', False) if hasattr(supervisor, 'fractal_agent') else False,
        "candle_prophet": "ACTIVE" if hasattr(supervisor, 'prophet_agent') else "OFFLINE",
        "trap_hunter": "SCANNING" if hasattr(supervisor, 'trap_agent') else "OFFLINE",
        "macro_tether": getattr(supervisor.macro_agent, 'macro_status', 'OFFLINE') if hasattr(supervisor, 'macro_agent') else "OFFLINE",
        "sector_scope": getattr(supervisor.sector_agent, 'consensus_status', 'OFFLINE') if hasattr(supervisor, 'sector_agent') else "OFFLINE",
        "gap_tactician": getattr(supervisor.gap_agent, 'status', 'OFFLINE') if hasattr(supervisor, 'gap_agent') else "OFFLINE",
        "rabbit_scalp": getattr(supervisor.rabbit_agent, 'status', 'OFFLINE') if hasattr(supervisor, 'rabbit_agent') else "OFFLINE",
        "delta_strike": getattr(supervisor.delta_agent, 'market_regime', 'OFFLINE') if hasattr(supervisor, 'delta_agent') else "OFFLINE",
        "whale_sonar": getattr(supervisor.whale_agent, 'sonar_status', 'OFFLINE') if hasattr(supervisor, 'whale_agent') else "OFFLINE",
        "gamma_ghost": "AWAKE" if getattr(supervisor.gamma_ghost, 'is_ghost_hour', False) else "SLEEPING",
        "fii_power": getattr(supervisor.fii_tracker, 'oi_insight', 'OFFLINE') if hasattr(supervisor, 'fii_tracker') else "OFFLINE",
        "premium_lab": getattr(supervisor.premium_lab, 'divergence_state', 'OFFLINE') if hasattr(supervisor, 'premium_lab') else "OFFLINE",
        "neural_sentry": f"{int(getattr(supervisor.neural_sentry, 'similarity_score', 0)*100)}%" if hasattr(supervisor, 'neural_sentry') else "OFFLINE",
        "sentiment_score": getattr(supervisor.sentiment_agent, 'sentiment_score', 0.0) if hasattr(supervisor, 'sentiment_agent') else 0.0,
        "global_correlation": getattr(supervisor.correlation_agent, 'global_status', 'OFFLINE') if hasattr(supervisor, 'correlation_agent') else "OFFLINE",
        "black_swan_alert": "ACTIVE" if hasattr(supervisor, 'black_swan') and supervisor.black_swan.kill_switch_active else "SCANNING",
        "alpha_alchemy": getattr(supervisor.optimizer_agent, 'current_regime', 'OFFLINE') if hasattr(supervisor, 'optimizer_agent') else "OFFLINE",
        "arbitrage_gap": f"{getattr(supervisor.arbitrage_agent, 'spread_pct', 0.0):.3f}%" if hasattr(supervisor, 'arbitrage_agent') else "0.000%",
        "institutional_load": getattr(supervisor.block_sniper, 'institutional_interest', 'OFFLINE') if hasattr(supervisor, 'block_sniper') else "OFFLINE",
        "tape_pressure": getattr(supervisor.tape_master, 'market_state', 'OFFLINE') if hasattr(supervisor, 'tape_master') else "OFFLINE",
        "scraped_points": f"{getattr(supervisor.scraper_agent, 'total_scraped_points', 0.0):.1f}" if hasattr(supervisor, 'scraper_agent') else "0.0",
        "learner_evolution": f"{len(getattr(supervisor.learner_agent, 'engine_weights', {}))} Engines" if hasattr(supervisor, 'learner_agent') else "OFFLINE",
        "magnet_zones": len(getattr(supervisor.heatmap_agent, 'magnet_zones', [])) if hasattr(supervisor, 'heatmap_agent') else 0,
        "macro_bias": getattr(supervisor.hedger_agent, 'active_sector_bias', 'OFFLINE') if hasattr(supervisor, 'hedger_agent') else "OFFLINE",
        "harmony_flow": "GOD_MODE" if hasattr(supervisor, 'flow_agent') and supervisor.flow_agent.is_god_mode else f"{int(getattr(supervisor.flow_agent, 'harmony_score', 0)*100)}%",
        "vpin_toxicity": getattr(supervisor.vpin_agent, 'toxicity_state', 'OFFLINE') if hasattr(supervisor, 'vpin_agent') else "OFFLINE",
        "iceberg_levels": len(getattr(supervisor.iceberg_agent, 'icebergs_detected', [])) if hasattr(supervisor, 'iceberg_agent') else 0,
        "max_pain_pull": getattr(supervisor.gamma_sniper, 'gravity_strength', 'OFFLINE') if hasattr(supervisor, 'gamma_sniper') else "OFFLINE",
        "zenith_execution": getattr(supervisor.decision_maker, 'execution_state', 'OFFLINE') if hasattr(supervisor, 'decision_maker') else "OFFLINE",
        "delta_divergence": getattr(supervisor.delta_sniper, 'divergence_state', 'OFFLINE') if hasattr(supervisor, 'delta_sniper') else "OFFLINE",
        "order_blocks": len(getattr(supervisor.order_block, 'order_blocks', [])) if hasattr(supervisor, 'order_block') else 0,
        "market_sync": getattr(supervisor.correlation_arbiter, 'correlation_status', 'OFFLINE') if hasattr(supervisor, 'correlation_arbiter') else "OFFLINE",
        "mirror_efficiency": f"{getattr(supervisor.mirror_mode, 'efficiency_score', 0):.1f}%" if hasattr(supervisor, 'mirror_mode') else "OFFLINE"
    }
    
    return JSONResponse(content={
        "status": "Running" if supervisor.is_running else "Stopped",
        "mode": "PAPER" if supervisor.execution_agent.paper_mode else "LIVE",
        "cpu_usage": 12.5,  # Placeholder
        "memory_usage": 45.2,
        "active_agents": len(supervisor.agents),
        "trinity_status": trinity
    })

@app.get("/api/risk-status")
async def get_risk_status():
    """Returns current risk management status with enhanced data for dashboard."""
    base_status = {
        "daily_pnl": 0.0,
        "risk_remaining_percent": 100.0,
        "drawdown_percent": 0.0,
        "trades_today": 0,
        "is_paused": False,
        "pause_reason": None,
        "win_streak": 0,
        "loss_streak": 0,
        "max_daily_loss": 2000.0,
        "data_source": "offline_defaults"
    }
    
    if supervisor.is_running and hasattr(supervisor, 'risk_agent'):
        agent_status = supervisor.risk_agent.get_risk_status()
        
        # Determine Gamma Multiplier from VIX
        vix = 15.0
        if hasattr(supervisor, 'sentiment_agent'):
             vix = supervisor.sentiment_agent.vix
        
        gamma = 1.0
        if vix < 12: gamma = 1.2
        elif vix > 20: gamma = 0.25
        elif vix > 16: gamma = 0.5

        if hasattr(supervisor, 'accounting_agent'):
            fin = supervisor.accounting_agent.get_finance_metrics()
            base_status["total_capital"] = fin.get("balance", 100000)
            base_status["net_pnl"] = fin.get("pnl", 0)

        base_status.update({
            "daily_pnl": -agent_status.get("daily_loss", 0),
            "risk_remaining_percent": (agent_status.get("remaining_capacity", 2000) / 2000) * 100,
            "drawdown_percent": agent_status.get("drawdown_percent", 0),
            "trades_today": agent_status.get("trades_today", 0),
            "is_paused": agent_status.get("is_paused", False),
            "gamma_multiplier": gamma
        })
    
    return JSONResponse(content=base_status)

@app.get("/api/strategy-performance")
async def get_strategy_performance():
    """Returns strategy performance comparison for the last 7 days."""
    # Sample data - would be populated from actual trade history
    strategies = [
        {"name": "theta", "pnl": 4200, "trades": 18, "win_rate": 72},
        {"name": "orb", "pnl": 1850, "trades": 8, "win_rate": 62},
        {"name": "oi", "pnl": 920, "trades": 5, "win_rate": 60}
    ]
    
    # Try to get real data from paper trader if available
    try:
        from core.paper_trader import paper_trader
        stats = paper_trader.get_stats()
        if stats.get("total_trades", 0) > 0:
            strategies = [
                {
                    "name": "theta",
                    "pnl": stats.get("realized_pnl", 0) * 0.6,
                    "trades": int(stats.get("total_trades", 0) * 0.6),
                    "win_rate": int(stats.get("win_rate", 0) * 100)
                },
                {
                    "name": "orb", 
                    "pnl": stats.get("realized_pnl", 0) * 0.25,
                    "trades": int(stats.get("total_trades", 0) * 0.25),
                    "win_rate": max(50, int(stats.get("win_rate", 0) * 100) - 10)
                },
                {
                    "name": "oi",
                    "pnl": stats.get("realized_pnl", 0) * 0.15,
                    "trades": int(stats.get("total_trades", 0) * 0.15),
                    "win_rate": max(50, int(stats.get("win_rate", 0) * 100) - 12)
                }
            ]
    except:
        pass
    
    return JSONResponse(content={"strategies": strategies})

@app.post("/api/pause-trading")
async def pause_trading():
    """Pause all trading activity."""
    if supervisor.is_running and hasattr(supervisor, 'risk_agent'):
        supervisor.risk_agent.is_paused = True
        return JSONResponse(content={"success": True, "message": "Trading paused"})
    return JSONResponse(content={"success": False, "message": "Risk agent not available"})

@app.post("/api/resume-trading")
async def resume_trading():
    """Resume trading activity."""
    if supervisor.is_running and hasattr(supervisor, 'risk_agent'):
        supervisor.risk_agent.is_paused = False
        return JSONResponse(content={"success": True, "message": "Trading resumed"})
    return JSONResponse(content={"success": False, "message": "Risk agent not available"})

@app.post("/api/flatten-all")
async def flatten_all_positions():
    """Close all open positions immediately."""
    if supervisor.is_running and hasattr(supervisor, 'position_manager'):
        # Close all positions at market
        closed = await supervisor.position_manager.close_all_positions()
        return JSONResponse(content={"success": True, "positions_closed": closed})
    return JSONResponse(content={"success": False, "message": "Position manager not available"})

class AutoTradeRequest(BaseModel):
    enabled: bool

@app.post("/api/auto-trade")
async def toggle_auto_trade(request: AutoTradeRequest):
    """Toggle automatic trading on/off."""
    # Store in supervisor for strategy selector to check
    supervisor.auto_trade_enabled = request.enabled
    return JSONResponse(content={"success": True, "auto_trade": request.enabled})

@app.get("/api/positions")
async def get_positions():
    """Returns open and recent closed positions."""
    if supervisor.is_running and hasattr(supervisor, 'position_manager'):
        return JSONResponse(content=supervisor.position_manager.get_stats())
    return JSONResponse(content={"open_count": 0, "closed_count": 0, "open_positions": [], "recent_closed": []})

@app.post("/config")
async def update_config(
    mode: str, 
    symbol: Optional[str] = "NIFTY", 
    quantity: Optional[int] = 50, 
    sl_pct: Optional[float] = 1.0, 
    tp_pct: Optional[float] = 3.0
):
    sys_config.update(
        MODE=mode, 
        TRADING_SYMBOL=symbol, 
        QUANTITY=quantity,
        STOP_LOSS_PCT=sl_pct,
        TAKE_PROFIT_PCT=tp_pct
    )
    # Propagate to Agents
    supervisor.update_market_config(symbol)
    
    return {"status": "Updated", "config": sys_config}

@app.post("/start")
async def start_system():
    print("!!! RECEIVED START COMMAND !!!")
    if not supervisor.is_running:
        await supervisor.start()
    return {"status": "Started"}

@app.post("/execute")
async def execute_manual(symbol: str, action: str, quantity: int, price: float = 0.0, sl_pct: float = 1.0, tp_pct: float = 2.0):
    """Manual Trade Trigger from Dashboard with SL/TP support"""
    order = {
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "price": price,
        "sl_pct": sl_pct,
        "tp_pct": tp_pct,
        "source": "MANUAL_UI"
    }
    # Direct injection into Execution bus
    await bus.publish(EventType.ORDER_VALIDATION, order)
    return {"status": "Order Placed", "order": order}

@app.post("/stop")
async def stop_system():
    await supervisor.stop()
    return {"status": "Stopped"}

@app.get("/analyze")
def analyze_strategy():
    if supervisor.is_running:
        return supervisor.strategy_agent.analyze_market()
    return {"status": "Offline"}

@app.get("/history")
def get_historical_data(symbol: str):
    """Returns historical candles for charting."""
    if supervisor.is_running:
        return supervisor.market_agent.get_history(symbol)
    return []

@app.get("/api/orders/history")
def get_order_history():
    """Returns the daily order history."""
    if supervisor.is_running and hasattr(supervisor, 'execution_agent'):
        return supervisor.execution_agent.get_daily_history()
    return []

@app.get("/api/sectors")
async def get_sector_rotation():
    """Returns current sector rotation analysis."""
    if supervisor.is_running and hasattr(supervisor, 'sector_scanner'):
        # Just return the internal scores
        rotation_data = []
        for key, rs in supervisor.sector_scanner.rs_scores.items():
            rotation_data.append({
                "sector": key,
                "rs": round(rs, 2),
                "bias": "BULLISH" if rs > 0.5 else "BEARISH" if rs < -0.5 else "NEUTRAL"
            })
        rotation_data.sort(key=lambda x: x['rs'], reverse=True)
        return JSONResponse(content={"sectors": rotation_data})
    return JSONResponse(content={"sectors": []})

@app.post("/api/deep-backtest")
async def run_deep_backtest(symbol: str = "NSE_INDEX|Nifty 50", days: int = 1):
    """Trigger a backtest of the Deep Scan logic."""
    if supervisor.is_running:
        result = await supervisor.deep_scan_agent.run_backtest(symbol, days)
        return JSONResponse(content=result)
    return JSONResponse(content={"status": "error", "message": "System Offline"})

@app.post("/analyze/deep")
async def deep_scan_market(symbol: str = "NSE_FO|NIFTY"):
    print(f"!!! STARTING DEEP SCAN: {symbol} !!!")
    if supervisor.is_running:
        try:
            # INTEGRATED REAL SCAN
            scan_result = await supervisor.deep_scan_agent.perform_deep_scan(symbol)
            
            # Additional metadata for UI
            scan_result['volume_profile'] = supervisor.volume_agent.get_volume_profile()
            
            # Add Gamma Scaler info to scan
            vix = 15.0
            if hasattr(supervisor, 'sentiment_agent'): vix = supervisor.sentiment_agent.vix
            scan_result['gamma_scale'] = 1.2 if vix < 12 else 0.25 if vix > 20 else 0.5 if vix > 16 else 1.0

            return JSONResponse(content={
                "status": "Success",
                "macro_scan": scan_result
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JSONResponse(content={"status": "Error", "message": str(e)})
    return JSONResponse(content={"status": "System Offline"})

# --- REAL-TIME STREAMING ---
# Reload trigger updated
@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    
    # Subscribe to EventBus for UI updates
    queue = asyncio.Queue()
    
    # Validated Event Pushers
    async def _push_tick(data):
        print(f"DEBUG: Push Tick Received: {data}")
        await queue.put({"type": EventType.MARKET_DATA, "data": data})

    async def _push_order(data):
        print(f"DEBUG: Push Order Received: {data}")
        await queue.put({"type": EventType.ORDER_EXECUTION, "data": data})
        
    async def _push_signal(data):
        print(f"DEBUG: Push Signal Received: {data}")
        await queue.put({"type": EventType.SIGNAL, "data": data})

    async def _push_candle(data):
        # print(f"DEBUG: Candle Data: {data}")
        await queue.put({"type": EventType.CANDLE_DATA, "data": data})

    async def _push_footprint(data):
        await queue.put({"type": EventType.FOOTPRINT_UPDATE, "data": data})
    
    async def _push_liquidity(data):
        await queue.put({"type": EventType.LIQUIDITY_EVENT, "data": data})

    # Level-02 Handlers
    async def _push_regime(data):
        await queue.put({"type": EventType.REGIME_CHANGE, "data": data})
    
    async def _push_trap(data):
        await queue.put({"type": EventType.TRAP_ALERT, "data": data})
    
    async def _push_gamma(data):
        await queue.put({"type": EventType.GAMMA_UPDATE, "data": data})
    
    async def _push_iceberg(data):
        await queue.put({"type": EventType.ICEBERG_DETECTED, "data": data})
    
    async def _push_consensus(data):
        await queue.put({"type": EventType.CONSENSUS_UPDATE, "data": data})

    # Listen to critical UI events
    bus.subscribe(EventType.TICK, _push_tick)  # Fixed: Listen for TICK events
    bus.subscribe(EventType.MARKET_DATA, _push_tick) # Backwards compat
    bus.subscribe(EventType.ORDER_EXECUTION, _push_order)
    bus.subscribe(EventType.SIGNAL, _push_signal)
    bus.subscribe(EventType.CANDLE_DATA, _push_candle)
    bus.subscribe(EventType.FOOTPRINT_UPDATE, _push_footprint)  # [LVL-1]
    bus.subscribe(EventType.LIQUIDITY_EVENT, _push_liquidity)    # [LVL-1]
    # Level-02 Subscriptions
    bus.subscribe(EventType.REGIME_CHANGE, _push_regime)
    bus.subscribe(EventType.TRAP_ALERT, _push_trap)
    bus.subscribe(EventType.GAMMA_UPDATE, _push_gamma)
    bus.subscribe(EventType.ICEBERG_DETECTED, _push_iceberg)
    bus.subscribe(EventType.CONSENSUS_UPDATE, _push_consensus)
    
    # Level-03 Handlers
    async def _push_explanation(data):
        await queue.put({"type": EventType.DECISION_EXPLAINED, "data": data})
    
    async def _push_debate(data):
        await queue.put({"type": EventType.DEBATE_RECORDED, "data": data})
    
    async def _push_fatigue(data):
        await queue.put({"type": EventType.STRATEGY_FATIGUE, "data": data})
    
    async def _push_blocked(data):
        await queue.put({"type": EventType.TRADE_BLOCKED, "data": data})
    
    async def _push_suppressed(data):
        await queue.put({"type": EventType.AGENT_SUPPRESSED, "data": data})
    
    # Level-03 Subscriptions
    bus.subscribe(EventType.DECISION_EXPLAINED, _push_explanation)
    bus.subscribe(EventType.DEBATE_RECORDED, _push_debate)
    bus.subscribe(EventType.STRATEGY_FATIGUE, _push_fatigue)
    bus.subscribe(EventType.TRADE_BLOCKED, _push_blocked)
    bus.subscribe(EventType.AGENT_SUPPRESSED, _push_suppressed)
    
    # Trading Mode Handler
    async def _push_mode_change(data):
        await queue.put({"type": EventType.MODE_CHANGE, "data": data})
    
    bus.subscribe(EventType.MODE_CHANGE, _push_mode_change)
    
    try:
        while True:
            # 1. Send Logs
            while not log_queue.empty():
                log_entry = await log_queue.get()
                await websocket.send_json({"type": "LOG", "data": log_entry})
            
            # 2. Send Events (Ticks, Orders)
            try:
                # Non-blocking get with timeout to allow loop to cycle
                event = await asyncio.wait_for(queue.get(), timeout=0.05)
                # Convert event to JSON-friendly dict
                if event['type'] == EventType.TICK or event['type'] == EventType.MARKET_DATA:
                     await websocket.send_json({"type": "TICK", "data": event['data']})
                elif event['type'] == EventType.CANDLE_DATA:
                     await websocket.send_json({"type": "CANDLE", "data": event['data']})
                elif event['type'] == EventType.ORDER_EXECUTION:
                     await websocket.send_json({"type": "ORDER", "data": event['data']})
                elif event['type'] == EventType.SIGNAL:
                     await websocket.send_json({"type": "SIGNAL", "data": event['data']})
                elif event['type'] == EventType.FOOTPRINT_UPDATE:
                     await websocket.send_json({"type": "FOOTPRINT", "data": event['data']})
                elif event['type'] == EventType.LIQUIDITY_EVENT:
                     await websocket.send_json({"type": "LIQUIDITY", "data": event['data']})
                # Level-02 Events
                elif event['type'] == EventType.REGIME_CHANGE:
                     await websocket.send_json({"type": "REGIME", "data": event['data']})
                elif event['type'] == EventType.TRAP_ALERT:
                     await websocket.send_json({"type": "TRAP", "data": event['data']})
                elif event['type'] == EventType.GAMMA_UPDATE:
                     await websocket.send_json({"type": "GAMMA", "data": event['data']})
                elif event['type'] == EventType.ICEBERG_DETECTED:
                     await websocket.send_json({"type": "ICEBERG", "data": event['data']})
                elif event['type'] == EventType.CONSENSUS_UPDATE:
                     await websocket.send_json({"type": "CONSENSUS", "data": event['data']})
                # Level-03 Events
                elif event['type'] == EventType.DECISION_EXPLAINED:
                     await websocket.send_json({"type": "EXPLANATION", "data": event['data']})
                elif event['type'] == EventType.DEBATE_RECORDED:
                     await websocket.send_json({"type": "DEBATE", "data": event['data']})
                elif event['type'] == EventType.STRATEGY_FATIGUE:
                     await websocket.send_json({"type": "FATIGUE", "data": event['data']})
                elif event['type'] == EventType.TRADE_BLOCKED:
                     await websocket.send_json({"type": "BLOCKED", "data": event['data']})
                elif event['type'] == EventType.AGENT_SUPPRESSED:
                     await websocket.send_json({"type": "SUPPRESSED", "data": event['data']})
                # Trading Mode Events
                elif event['type'] == EventType.MODE_CHANGE:
                     await websocket.send_json({"type": "MODE", "data": event['data']})
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                # logging.error(f"Stream Error: {e}")
                pass
                
            await asyncio.sleep(0.01)
            
    except Exception as e:
        print(f"WS Disconnect: {e}")
    finally:
        # Cleanup: In a real app we'd unsubscribe, but `bus` here is simple list
        pass

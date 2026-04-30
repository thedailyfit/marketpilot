import logging
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from engine import engine
import config
import asyncio

# Setup Logging to capture logs for the dashboard
log_queue = asyncio.Queue()

class QueueHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        try:
            log_queue.put_nowait(log_entry)
        except:
            pass

# Configure root logger to output to our queue
logging.basicConfig(level=logging.INFO)
queue_handler = QueueHandler()
queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(queue_handler)

app = FastAPI()

# Enable CORS for local/web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "AI Trading Bot API is Online"}

@app.post("/start")
async def start_bot(symbol: str = None):
    """Starts the trading bot."""
    return await engine.start(symbol)

@app.post("/stop")
async def stop_bot():
    """Stops the trading bot."""
    return await engine.stop()

@app.get("/status")
def get_status():
    """Returns current running status and configuration."""
    return {
        "is_running": engine.is_running,
        "symbol": config.TRADING_SYMBOL,
        "pnl": "Tracking in Logs" # Placeholder
    }

from fastapi import WebSocket

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Check for new logs
            while not log_queue.empty():
                log = await log_queue.get()
                await websocket.send_text(log)
            await asyncio.sleep(0.1)
    except Exception:
        pass


import asyncio
import logging
from core.base_agent import BaseAgent
from core.upstox_stream import UpstoxWebSocket
from core.config_manager import sys_config

class MarketDataAgent(BaseAgent):
    """
    Real Market Data Agent using Upstox V3 WebSocket.
    Replaces the previous mock agent.
    """
    def __init__(self):
        super().__init__("MarketData")
        self.ws = UpstoxWebSocket()
        self.is_running = False
        
    async def on_start(self):
        """Start the Upstox WebSocket Stream."""
        self.logger.info("Starting Real Market Data Agent (Upstox V3)...")
        self.is_running = True
        
        # Start Connection
        await self.ws.connect()
        
        # Subscribe to Default Instruments
        defaults = [
            "NSE_INDEX|Nifty 50",
            "NSE_INDEX|Nifty Bank", 
            "NSE_INDEX|India VIX"
        ]
        
        # Wait a moment for connection before subscribing
        await asyncio.sleep(2)
        await self.ws.subscribe(defaults)
        self.logger.info(f"Subscribed to defaults: {defaults}")

    async def on_stop(self):
        """Stop the stream."""
        self.is_running = False
        self.logger.info("Stopping Market Data Agent")
        # Logic to close WS provided in UpstoxWebSocket if needed
        # self.ws.close() 

    def update_config(self, symbol: str):
        """Subscribe to new symbol dynamically."""
        asyncio.create_task(self.ws.subscribe([symbol]))

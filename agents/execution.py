import asyncio
import logging
import upstox_client
import config
import json
import os
from datetime import datetime
from config import API_KEY, API_SECRET, REDIRECT_URI, QUANTITY, TRADING_SYMBOL

ORDER_HISTORY_FILE = "data/order_history.json"

class ExecutionAgent:
    def __init__(self, input_queue):
        self.logger = logging.getLogger("Execution")
        self.input_queue = input_queue
        self.api_client = None 
        # Ensure data dir exists
        os.makedirs(os.path.dirname(ORDER_HISTORY_FILE), exist_ok=True)

    async def start(self):
        self.logger.info("Execution Listener Started")
        asyncio.create_task(self._process_orders())

    async def _process_orders(self):
        while True:
            signal = await self.input_queue.get()
            await self.execute_order(signal)
            self.input_queue.task_done()

    async def initialize(self):
        self.logger.info("Initializing Execution Agent...")
        try:
             configuration = upstox_client.Configuration()
             configuration.access_token = config.ACCESS_TOKEN
             self.api_client = upstox_client.ApiClient(configuration)
             self.logger.info("Upstox Connection Successfully Established!")
        except Exception as e:
             self.logger.error(f"Failed to connect to Upstox: {e}")

    def get_daily_history(self):
        """Returns the list of orders from the history file."""
        if not os.path.exists(ORDER_HISTORY_FILE):
            return []
        try:
            with open(ORDER_HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def save_order(self, order_details):
        """Appends a new order to the history file."""
        history = self.get_daily_history()
        history.append(order_details)
        try:
            with open(ORDER_HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save order history: {e}")

    def place_upstox_order(self, signal):
        try:
            api_instance = upstox_client.OrderApi(self.api_client)
            
            # Determine Transaction Type
            trans_type = 'BUY' if signal['action'] == 'BUY' else 'SELL'
            
            # Create Order Request
            body = upstox_client.PlaceOrderRequest(
                quantity=QUANTITY,
                product='I', # Intraday
                validity='DAY',
                price=0.0, # Market Order
                tag='AI_BOT',
                instrument_token=TRADING_SYMBOL,
                order_type='MARKET',
                transaction_type=trans_type,
                disclosed_quantity=0,
                trigger_price=0.0,
                is_amo=False
            )
            
            # Execute
            api_response = api_instance.place_order(body, api_version='2.0')
            order_id = api_response.order_id
            self.logger.info(f"🚀 REAL {trans_type} ORDER SENT! ID: {order_id}")
            
            # Persist Order
            order_record = {
                "id": order_id,
                "timestamp": datetime.now().isoformat(),
                "symbol": TRADING_SYMBOL,
                "action": trans_type,
                "quantity": QUANTITY,
                "price": "MARKET", # Real filled price would require fetching order book later
                "status": "SENT"
            }
            self.save_order(order_record)
            
            return api_response

        except Exception as e:
            self.logger.error(f"❌ ORDER FAILED: {e}")
            return None

    async def execute_order(self, signal):
        self.logger.info(f"Received Execution Signal: {signal['action']} | Reason: {signal.get('reason', 'Entry')}")
        
        # Call Real API
        await asyncio.to_thread(self.place_upstox_order, signal)
        
        return {"status": "SENT"}

import csv
import os
import logging
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

class ComplianceAgent(BaseAgent):
    def __init__(self):
        super().__init__("ComplianceAgent")
        self.log_dir = "data/logs"
        self.log_file = os.path.join(self.log_dir, "trade_log.csv")
        self._ensure_log_file()

    def _ensure_log_file(self):
        """Creates the log directory and file if they don't exist."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Symbol", "Action", "Quantity", "Price", "Status", "Mode", "StrategyID", "OrderID"])

    async def on_start(self):
        self.logger.info("Compliance Audit Engine Started")
        bus.subscribe(EventType.ORDER_EXECUTION, self.log_trade)

    async def on_stop(self):
        pass

    async def log_trade(self, trade_data: dict):
        """Logs trade execution details to CSV."""
        try:
            timestamp = datetime.now().isoformat()
            
            row = [
                timestamp,
                trade_data.get('symbol', 'UNKNOWN'),
                trade_data.get('action', 'UNKNOWN'),
                trade_data.get('quantity', 0),
                trade_data.get('fill_price', trade_data.get('price', 0)),
                trade_data.get('status', 'UNKNOWN'),
                trade_data.get('mode', 'PAPER'),
                trade_data.get('strategy_id', 'MANUAL'),
                trade_data.get('order_id', 'N/A')
            ]
            
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
                
            self.logger.info(f"Trade Logged: {trade_data.get('order_id')}")
            
        except Exception as e:
            self.logger.error(f"Failed to log trade: {e}")

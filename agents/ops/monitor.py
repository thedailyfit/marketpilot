import time
# import psutil # Removed due to missing dependency
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

class MonitorAgent(BaseAgent):
    def __init__(self):
        super().__init__("MonitorAgent")
        self.metrics = {
            "start_time": time.time(),
            "ticks_processed": 0,
            "orders_executed": 0,
            "last_tick_latency": 0,
            "cpu_usage": 0.0,
            "ram_usage": 0.0
        }

    async def on_start(self):
        bus.subscribe(EventType.MARKET_DATA, self.on_tick)
        bus.subscribe(EventType.ORDER_EXECUTION, self.on_order)
        bus.subscribe(EventType.SYSTEM_STATUS, self.on_status)

    async def on_stop(self):
        pass

    async def on_tick(self, tick: dict):
        self.metrics["ticks_processed"] += 1
        # Latency check (Time now - Tick Generation Time)
        self.metrics["last_tick_latency"] = time.time() - tick.get('timestamp', time.time())
        
        # Periodic System Check (every 100 ticks ~ 1 min)
        if self.metrics["ticks_processed"] % 100 == 0:
            self._update_system_stats()

    async def on_order(self, result: dict):
        self.metrics["orders_executed"] += 1

    async def on_status(self, status: dict):
        self.logger.info(f"System Status Update: {status}")

    def _update_system_stats(self):
        # self.metrics["cpu_usage"] = psutil.cpu_percent()
        # self.metrics["ram_usage"] = psutil.virtual_memory().percent
        self.metrics["cpu_usage"] = 0.0 # Dummy
        self.metrics["ram_usage"] = 0.0 # Dummy

    def get_metrics(self):
        return self.metrics

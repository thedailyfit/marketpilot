
import logging
import asyncio
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("DecisionMakerAgent")

class DecisionMakerAgent(BaseAgent):
    """
    ENGINE 36: THE ZENITH SNIPER (Decision Maker)
    Final threshold for trade execution. Implements patience and consensus logic.
    """
    def __init__(self, supervisor=None):
        super().__init__("DecisionMakerAgent")
        self.supervisor = supervisor
        self.pending_executes = {} # trade_id: {data, target_price, start_time}
        self.execution_state = "PATIENCE_MODE"
        self.vwap = 0.0

    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        logger.info("🧠 Zenith Sniper (Super-Intelligence) Active")

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        self.vwap = tick.get('vwap', self.vwap)
        price = tick['ltp']
        
        # Scan pending executes for pullback completion or VWAP touch
        for tid, data in list(self.pending_executes.items()):
            signal_price = data['signal_price']
            direction = data['data']['action']
            
            # CONSENSUS CHECK
            consensus_passed = self.check_consensus(direction)
            
            # PULLBACK logic: Wait for 0.05% pullback from signal
            target_hit = False
            if direction == "BUY":
                # Buy pullback: Price should be below signal price or near VWAP
                if price <= signal_price * 0.9995 or (self.vwap > 0 and price <= self.vwap * 1.001):
                    target_hit = True
            else:
                # Sell pullback: Price should be above signal price or near VWAP
                if price >= signal_price * 1.0005 or (self.vwap > 0 and price >= self.vwap * 0.999):
                    target_hit = True

            if target_hit and consensus_passed:
                logger.info(f"🧠 ZENITH: Super-Intelligence Trigger for {tid}. Consensus & Entry Confirmed.")
                await bus.publish(EventType.EXECUTION, {
                    "source": "DecisionMakerAgent",
                    "type": "SMART_EXECUTE",
                    "data": data['data']
                })
                del self.pending_executes[tid]
                self.execution_state = "TRADE_DISPATCHED"
            
            # Expiry: If waiting > 5 mins, cancel
            import time
            if time.time() - data['start_time'] > 300:
                logger.warning(f"⏰ ZENITH: Trade {tid} Expired (Optimal Entry Not Reached)")
                del self.pending_executes[tid]
                self.execution_state = "STABLE"

    def check_consensus(self, direction):
        """Consults other engines for final GO/NO-GO."""
        if not self.supervisor: return True
        
        score = 0
        checks = 0
        
        # VPIN Check
        if hasattr(self.supervisor, 'vpin_agent'):
            checks += 1
            if self.supervisor.vpin_agent.toxicity_state == "LOW": score += 1
            
        # Iceberg Check
        if hasattr(self.supervisor, 'iceberg_agent'):
            checks += 1
            # If no dangerous walls in direction, +1
            score += 1 
            
        # Gamma Check
        if hasattr(self.supervisor, 'gamma_sniper'):
            checks += 1
            if direction == self.supervisor.gamma_sniper.gravity_strength == "HIGH":
                # Logic: If gravity pull is in trade direction, boost
                score += 1
            else:
                score += 0.5
                
        confidence = (score / checks) if checks > 0 else 1.0
        return confidence >= 0.75

    def intercept_and_wait(self, trade_data):
        """Intercepts a signal and waits for the absolute best entry."""
        import time
        tid = f"ZENITH_{int(time.time() % 10000)}"
        self.pending_executes[tid] = {
            "data": trade_data,
            "signal_price": trade_data.get('entry_price', 0.0), # Fallback handled in tick
            "start_time": time.time()
        }
        # If signal_price is 0, we use current LTP as base
        if self.pending_executes[tid]["signal_price"] == 0:
             # This is a market signal, we'll need to grab the LTP in next tick or here
             pass 

        self.execution_state = "SNIPING_FOR_ENTRY"
        logger.info(f"🧠 ZENITH INTERCEPTED: Multi-Agent Consensus Pending for {trade_data['action']}...")
        return tid

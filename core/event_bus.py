import asyncio
import logging
from enum import Enum
from typing import Dict, List, Callable, Any

class EventType(Enum):
    MARKET_DATA = "MARKET_DATA"
    TICK = "TICK"  # [NEW] Real-time tick data
    CANDLE = "CANDLE" # [NEW] Real-time candle
    CANDLE_DATA = "CANDLE_DATA"  # Aggregated OHLCV
    MARKET_FEATURES = "MARKET_FEATURES" # Greeks & Indicators
    ANALYSIS = "ANALYSIS" # [NEW] Higher level analysis events
    SIGNAL = "SIGNAL"
    ORDER_VALIDATION = "ORDER_VALIDATION"
    ORDER_EXECUTION = "ORDER_EXECUTION"
    RISK_CHECK = "RISK_CHECK"
    SYSTEM_STATUS = "SYSTEM_STATUS"
    LOG = "LOG"
    NEWS_ALERT = "NEWS_ALERT"  # [NEW] News sentiment alerts
    VIX_SPIKE = "VIX_SPIKE"    # [NEW] VIX volatility alerts
    FOOTPRINT_UPDATE = "FOOTPRINT_UPDATE" # [NEW LVL-1] Footprint/Orderflow data
    LIQUIDITY_EVENT = "LIQUIDITY_EVENT"   # [NEW LVL-1] Big trade/Absorption
    REPLAY_TICK = "REPLAY_TICK"           # [NEW LVL-1] Historical tick injection
    # Level-02 Intelligence Events
    REGIME_CHANGE = "REGIME_CHANGE"       # [LVL-2] Market regime transition
    TRAP_ALERT = "TRAP_ALERT"             # [LVL-2] Trap detection alert
    GAMMA_UPDATE = "GAMMA_UPDATE"         # [LVL-2] Dealer gamma exposure update
    ICEBERG_DETECTED = "ICEBERG_DETECTED" # [LVL-2] Hidden order detected
    CONSENSUS_UPDATE = "CONSENSUS_UPDATE" # [LVL-2] Agent vote weight change
    # Level-03 Meta-Intelligence Events
    DECISION_EXPLAINED = "DECISION_EXPLAINED"  # [LVL-3] Plain-English reasoning
    DEBATE_RECORDED = "DEBATE_RECORDED"        # [LVL-3] Agent debate snapshot
    STRATEGY_FATIGUE = "STRATEGY_FATIGUE"      # [LVL-3] Edge decay alert
    TRADE_BLOCKED = "TRADE_BLOCKED"            # [LVL-3] Self-regulation block
    AGENT_SUPPRESSED = "AGENT_SUPPRESSED"      # [LVL-3] Low reliability agent
    # Trading Mode Events
    MODE_CHANGE = "MODE_CHANGE"                # Trading mode switched

class EventBus:
    def __init__(self):
        self.subscribers: Dict[EventType, List[Callable]] = {event_type: [] for event_type in EventType}
        self.logger = logging.getLogger("EventBus")

    def subscribe(self, event_type: EventType, callback: Callable):
        """Register a callback for a specific event type."""
        self.subscribers[event_type].append(callback)
        self.logger.debug(f"Subscribed to {event_type.name}")

    async def publish(self, event_type: EventType, data: Any):
        """Publish an event to all subscribers."""
        if event_type in self.subscribers:
            subs = self.subscribers[event_type]
            # Debug: only print for TICK events to avoid spam
            if event_type == EventType.TICK and len(subs) > 0:
                print(f"EVENTBUS_PUBLISH: {event_type.name} -> {len(subs)} subscriber(s)")
            # Create a task for each subscriber to run asynchronously
            for callback in subs:
                asyncio.create_task(self._safe_callback(callback, data))

    async def _safe_callback(self, callback: Callable, data: Any):
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as e:
            cb_name = getattr(callback, "__name__", str(callback))
            import traceback
            traceback.print_exc()
            self.logger.error(f"Error in event handler [{cb_name}]: {e}")

# Global Event Bus Instance
bus = EventBus()

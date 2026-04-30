import asyncio
import logging
from typing import Optional
from dataclasses import asdict
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from core.data_models import Signal
from agents.trading.strategies.scalper import ScalpingStrategy
from agents.trading.strategies.gamma_blast import GammaBlastStrategy

class StrategyAgent(BaseAgent):
    def __init__(self):
        super().__init__("StrategyAgent")
        # Multi-Strategy Engine
        self.strategies = [
            ScalpingStrategy(),
            GammaBlastStrategy()
        ]
        
    async def on_start(self):
        names = [s.name for s in self.strategies]
        self.logger.info(f"Strategy Engine Started. Active: {names}")
        bus.subscribe(EventType.MARKET_DATA, self.on_tick)
        bus.subscribe(EventType.CANDLE_DATA, self.on_candle)
        bus.subscribe(EventType.MARKET_FEATURES, self.on_features)

    async def on_stop(self):
        pass

    async def on_tick(self, data: dict):
        """High-Frequency Tick Logic (Gamma Blast)"""
        try:
            for strategy in self.strategies:
                # GammaBlast relies on Ticks
                if hasattr(strategy, 'on_tick'):
                    signal = strategy.on_tick(data)
                    if signal:
                       await self._publish_signal(signal)
        except Exception as e:
            self.logger.error(f"Strategy Tick Error: {e}")

    async def on_candle(self, data: dict):
        pass

    async def on_features(self, data: dict):
        """Primary signal generation loop based on features (Scalper)."""
        try:
            for strategy in self.strategies:
                # Scalper relies on Features
                if hasattr(strategy, 'on_features'):
                     signal = strategy.on_features(data)
                     if signal:
                        await self._publish_signal(signal)
                
        except Exception as e:
            self.logger.error(f"Strategy Feature Error: {e}")

    async def _publish_signal(self, signal):
        """Helper to publish signals."""
        self.logger.info(f"SIGNAL GENERATED: {signal['action']} {signal.get('strategy')} ({signal.get('reason')})")
        
        # Publish Signal
        # Use dict directly if it's already dict (GammaBlast returns dict)
        if hasattr(signal, 'to_dict'):
            sig_dict = asdict(signal)
        else:
            sig_dict = signal
            
        if 'quantity' not in sig_dict:
            sig_dict['quantity'] = 1 
            
        await bus.publish(EventType.SIGNAL, sig_dict)

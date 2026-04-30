import asyncio
import logging
from abc import ABC, abstractmethod
from core.event_bus import bus, EventType

class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name
        self.is_running = False
        self.logger = logging.getLogger(name)

    async def start(self):
        """Start the agent's main loop."""
        if self.is_running:
            self.logger.warning(f"Agent {self.name} is already running.")
            return
        
        self.is_running = True
        self.logger.info(f"Starting Agent: {self.name}")
        await self.on_start()
        
        # Publish System Status
        await bus.publish(EventType.SYSTEM_STATUS, {"agent": self.name, "status": "STARTED"})

    async def stop(self):
        """Stop the agent."""
        if not self.is_running:
            return
            
        self.is_running = False
        self.logger.info(f"Stopping Agent: {self.name}")
        await self.on_stop()
        
        # Publish System Status
        await bus.publish(EventType.SYSTEM_STATUS, {"agent": self.name, "status": "STOPPED"})

    @abstractmethod
    async def on_start(self):
        """Hook for startup logic (e.g., connecting to db/api)."""
        pass

    @abstractmethod
    async def on_stop(self):
        """Hook for shutdown logic (e.g., closing connections)."""
        pass
    
    async def health_check(self):
        """Return status string."""
        return "OK" if self.is_running else "STOPPED"

"""
Zone Memory Management
Persists Institutional Zones across sessions.
"""
import logging
import json
from pathlib import Path
from typing import List, Dict
from .zone_engine import InstitutionalZone, zone_engine

class ZoneMemory:
    """
    Stores zones to disk and loads them on startup.
    Ages zones over time.
    """
    def __init__(self):
        self.logger = logging.getLogger("ZoneMemory")
        self.data_path = Path("data/volume/zones.json")
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        
    def save_zones(self):
        """Save active zones to JSON."""
        zones = zone_engine.zones
        data = []
        for z in zones:
            data.append({
                "zone_id": z.zone_id,
                "poc": z.poc,
                "upper": z.upper_bound,
                "lower": z.lower_bound,
                "strength": z.strength,
                "created": z.created_at,
                "fresh": z.is_fresh,
                "touches": z.touch_count,
                "status": z.status
            })
            
        try:
            with open(self.data_path, 'w') as f:
                json.dump(data, f, indent=2)
            self.logger.info(f"Saved {len(data)} zones to memory.")
        except Exception as e:
            self.logger.error(f"Failed to save zones: {e}")
            
    def load_zones(self):
        """Load zones from JSON."""
        if not self.data_path.exists():
            return
            
        try:
            with open(self.data_path, 'r') as f:
                data = json.load(f)
                
            loaded_zones = []
            for d in data:
                z = InstitutionalZone(
                    zone_id=d['zone_id'],
                    poc=d['poc'],
                    upper_bound=d['upper'],
                    lower_bound=d['lower'],
                    strength=d['strength'],
                    created_at=d['created'],
                    is_fresh=d['fresh'],
                    touch_count=d['touches'],
                    status=d['status']
                )
                loaded_zones.append(z)
                
            zone_engine.zones = loaded_zones
            self.logger.info(f"Loaded {len(loaded_zones)} zones from memory.")
            
        except Exception as e:
            self.logger.error(f"Failed to load zones: {e}")

# Singleton
zone_memory = ZoneMemory()

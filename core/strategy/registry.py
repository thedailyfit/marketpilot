"""
Strategy Registry
Manages strategy versions and configurations.
"""
import logging
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

@dataclass
class StrategyVersion:
    """Configuration for a specific version."""
    version_id: str
    created_at: int
    parameters: Dict
    status: str = "ACTIVE" # ACTIVE, DISABLED, DEPRECATED
    notes: str = ""

@dataclass
class StrategyConfig:
    """Master record for a strategy."""
    name: str
    active_version: str
    versions: Dict[str, StrategyVersion] = field(default_factory=dict) # version_id -> Version

    def to_dict(self):
        return {
            "name": self.name,
            "active_version": self.active_version,
            "versions": {k: asdict(v) for k, v in self.versions.items()}
        }

class StrategyRegistry:
    """
    Central database for strategy configurations.
    """
    def __init__(self):
        self.logger = logging.getLogger("StrategyRegistry")
        self.data_path = Path("data/strategies/registry.json")
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.strategies: Dict[str, StrategyConfig] = {}
        self._load()
        
    def register_strategy(self, name: str, initial_params: Dict) -> str:
        """Register a new strategy or return existing."""
        if name in self.strategies:
            return self.strategies[name].active_version
            
        version_id = "v1.0.0"
        version = StrategyVersion(
            version_id=version_id,
            created_at=int(datetime.now().timestamp()),
            parameters=initial_params,
            notes="Initial Release"
        )
        
        config = StrategyConfig(
            name=name,
            active_version=version_id,
            versions={version_id: version}
        )
        
        self.strategies[name] = config
        self._save()
        self.logger.info(f"Registered New Strategy: {name} ({version_id})")
        return version_id
        
    def get_active_params(self, name: str) -> Optional[Dict]:
        """Get parameters for the active version."""
        if name not in self.strategies:
            return None
        
        config = self.strategies[name]
        active_ver = config.versions.get(config.active_version)
        if active_ver and active_ver.status == "ACTIVE":
            return active_ver.parameters
        return None

    def promote_version(self, name: str, new_params: Dict, notes: str = "") -> str:
        """Create and activate a new version."""
        if name not in self.strategies:
            raise ValueError(f"Strategy {name} not found")
            
        config = self.strategies[name]
        
        # Calculate new version ID (Simple increment)
        current = config.active_version
        try:
            # Assumes vX.Y.Z format
            parts = current.replace("v", "").split(".")
            minor = int(parts[1]) + 1
            new_id = f"v{parts[0]}.{minor}.{parts[2]}"
        except:
            new_id = f"{current}_next"
            
        new_version = StrategyVersion(
            version_id=new_id,
            created_at=int(datetime.now().timestamp()),
            parameters=new_params,
            notes=notes
        )
        
        config.versions[new_id] = new_version
        config.active_version = new_id
        self._save()
        
        self.logger.info(f"🚀 Promoted {name} to {new_id}")
        return new_id

    def rollback_version(self, name: str) -> Optional[str]:
        """
        Revert to the previous stable version.
        Returns new active version ID.
        """
        if name not in self.strategies:
            return None
            
        config = self.strategies[name]
        current_id = config.active_version
        
        # Mark current as DISABLED
        if current_id in config.versions:
            config.versions[current_id].status = "DISABLED"
            config.versions[current_id].notes += " [ROLLED BACK]"
            
        # Find previous version (simple: sort by keys?)
        # Keys are strings, so sorting v1.10.0 vs v1.2.0 might be tricky.
        # Ideally track 'previous_version' or use timestamp.
        
        sorted_versions = sorted(
            [v for v in config.versions.values() if v.status == "ACTIVE" or v.version_id != current_id],
            key=lambda x: x.created_at,
            reverse=True
        )
        
        # Filter out the one we just disabled if it's still in the list (logic check)
        candidates = [v for v in sorted_versions if v.version_id != current_id and v.status == "ACTIVE"]
        
        if not candidates:
            self.logger.critical(f"❌ No stable version to rollback to for {name}!")
            return None
            
        prev_stable = candidates[0]
        config.active_version = prev_stable.version_id
        self._save()
        
        self.logger.warning(f"🔄 Rolled back {name} to {prev_stable.version_id}")
        return prev_stable.version_id

    def _save(self):
        try:
            with open(self.data_path, 'w') as f:
                # Need custom encoder? dataclasses usually handle simple types.
                # using .to_dict() methods
                data = {k: v.to_dict() for k, v in self.strategies.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save registry: {e}")

    def _load(self):
        if not self.data_path.exists():
            return
        try:
            with open(self.data_path, 'r') as f:
                data = json.load(f)
                for name, d in data.items():
                    # Reconstruct objects
                    versions = {}
                    for vid, vdata in d['versions'].items():
                        versions[vid] = StrategyVersion(**vdata)
                    
                    config = StrategyConfig(
                        name=d['name'],
                        active_version=d['active_version'],
                        versions=versions
                    )
                    self.strategies[name] = config
        except Exception as e:
            self.logger.error(f"Failed to load registry: {e}")

# Singleton
strategy_registry = StrategyRegistry()

import asyncio
import hashlib
import logging
import threading
from typing import Optional, Dict, Any
from pathlib import Path
import yaml
from pydantic import ValidationError

from .models import RoutingTable

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Manages loading and hot-reloading of the routing configuration.
    It reads from a YAML file, caching it in-memory.
    Periodically checks the file's SHA-256 checksum, and if changed,
    it reloads the YAML file.
    It also allows DB overrides, mocking this logic for now.
    """

    def __init__(self, config_path: str = "config/routing_config.yaml", reload_interval: int = 60):
        self._config_path = Path(config_path)
        self._reload_interval = reload_interval
        
        self._routing_table: Optional[RoutingTable] = None
        self._file_hash: Optional[str] = None
        
        # Ensures thread-safe reads and writes to the memory cache.
        self._lock = threading.RLock()
        
        self._watcher_task: Optional[asyncio.Task] = None
        
    def _calculate_checksum(self) -> Optional[str]:
        """Calculates the SHA-256 checksum of the config file."""
        if not self._config_path.exists():
            return None
        
        hasher = hashlib.sha256()
        try:
            with open(self._config_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except OSError as e:
            logger.error(f"Failed to read configs: {e}")
            return None
            
    def _load_yaml(self) -> Dict[str, Any]:
        """Reads and parses the config YAML."""
        if not self._config_path.exists():
            raise FileNotFoundError(f"Routing config file not found: {self._config_path}")
            
        with open(self._config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _fetch_db_overrides(self) -> Dict[str, Any]:
        """
        Mock function to fetch overrides from the database.
        In a real scenario, this would query the DB asynchronously 
        and return a structure compatible with `RoutingTable`.
        """
        # Mocking an empty DB override for now. 
        # Future phases will implement DB overrides.
        return {}

    def _merge_configs(self, yaml_config: Dict[str, Any], db_overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Merges DB overrides into the base YAML configuration."""
        # For phase 1, we just return yaml config, ignoring empty DB merge logic.
        # Deep dictionary merge logic to combine overrides will reside here in Phase 2+.
        merged_config = yaml_config.copy()
        
        # Trivial logic representing DB overlay
        if db_overrides:
             merged_config.update(db_overrides)
             
        return merged_config
        
    def _reload_config(self) -> None:
        """
        Calculates checksum, reloads YAML + DB config if changes found, 
        and updates the cached model thread-safely.
        """
        current_hash = self._calculate_checksum()
        
        if current_hash is None:
            logger.warning("Config file could not be read or does not exist.")
            return

        # Same config, do not do heavy parsing
        if current_hash == self._file_hash and self._routing_table is not None:
             return
             
        logger.info(f"Detected configuration change. Reloading config from {self._config_path}...")
        
        try:
            yaml_config = self._load_yaml()
            db_overrides = self._fetch_db_overrides()
            
            merged_dict = self._merge_configs(yaml_config, db_overrides)
            new_routing_table = RoutingTable.model_validate(merged_dict)
            
            with self._lock:
                self._routing_table = new_routing_table
                self._file_hash = current_hash
                
            logger.info("Successfully reloaded routing configuration.")
            
        except ValidationError as e:
            logger.error(f"Config validation error: {e}")
        except yaml.YAMLError as e:
             logger.error(f"YAML parsing error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error when reloading configuration: {e}")

    async def _watch_loop(self) -> None:
        """Async loop to continuously poll for configuration changes."""
        while True:
            try:
                await asyncio.sleep(self._reload_interval)
                # Ensure the synchronous parsing runs in a threadpool so it doesn't block the loop
                await asyncio.to_thread(self._reload_config)
            except asyncio.CancelledError:
                break
            except Exception as e:
                 logger.error(f"Error in config watcher loop: {e}")
                 
    def start_watcher(self) -> None:
        """Initializes initial config and starts the async background watcher loop."""
        # Initial synchronous load before returning control
        self._reload_config()
        
        try:
            loop = asyncio.get_running_loop()
            self._watcher_task = loop.create_task(self._watch_loop())
        except RuntimeError:
             # If no event loop is running (e.g. running outside FastAPI)
             logger.warning("No running asyncio loop. Config auto-reload watcher not started.")

    async def stop_watcher(self) -> None:
         """Gracefully stops the background watcher task."""
         if self._watcher_task:
             self._watcher_task.cancel()
             try:
                 await self._watcher_task
             except asyncio.CancelledError:
                 pass
             
    def get_routing_table(self) -> RoutingTable:
        """
        Returns the thread-safe copy of the cached routing config.
        Raises an error if missing.
        """
        with self._lock:
            if self._routing_table is None:
                 raise RuntimeError("RoutingTable is not loaded. Ensure config file is present and manager has been initialized.")
            return self._routing_table

# Dependency Injection usage point
_config_manager_instance: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """Singleton pattern to fetch manager across the API lifecycle."""
    global _config_manager_instance
    if _config_manager_instance is None:
         _config_manager_instance = ConfigManager()
    return _config_manager_instance

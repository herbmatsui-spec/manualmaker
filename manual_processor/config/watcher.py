"""
Configuration file watcher for hot reload.
Monitors config file changes and reloads settings automatically.
"""

import logging
import time
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """Handler for config file changes"""

    def __init__(self, callback: Callable[[], None], cooldown_seconds: float = 1.0):
        """
        Initialize handler.
        
        Args:
            callback: Function to call when config changes
            cooldown_seconds: Minimum seconds between reloads
        """
        super().__init__()
        self.callback = callback
        self.cooldown_seconds = cooldown_seconds
        self._last_reload = 0.0
        self._lock = threading.Lock()

    def on_modified(self, event):
        """Handle file modification event"""
        if event.is_directory:
            return

        # Check if it's a config file
        event_path = Path(event.src_path)
        if event_path.name not in ("config.yaml", "config.yml", "pii_patterns.yaml"):
            return

        # Debounce: only reload if cooldown has passed
        with self._lock:
            now = time.time()
            if now - self._last_reload < self.cooldown_seconds:
                return
            self._last_reload = now

        logger.info(f"Config file changed: {event_path}")
        try:
            self.callback()
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")


class ConfigWatcher:
    """
    Watches configuration files for changes and reloads settings.
    
    Usage:
        watcher = ConfigWatcher(config_path, reload_callback)
        watcher.start()
        # ... later ...
        watcher.stop()
    """

    def __init__(
        self,
        config_path: Path,
        callback: Callable[[], None],
        cooldown_seconds: float = 1.0,
    ):
        """
        Initialize watcher.
        
        Args:
            config_path: Path to config file to watch
            callback: Function to call when config changes
            cooldown_seconds: Minimum seconds between reloads
        """
        self.config_path = config_path
        self.callback = callback
        self.cooldown_seconds = cooldown_seconds
        self._observer: Optional[Observer] = None
        self._handler: Optional[ConfigFileHandler] = None

    def start(self) -> None:
        """Start watching config file"""
        if self._observer and self._observer.is_alive():
            logger.warning("Config watcher is already running")
            return

        watch_dir = self.config_path.parent
        self._handler = ConfigFileHandler(self.callback, self.cooldown_seconds)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(watch_dir), recursive=False)
        self._observer.start()

        logger.info(f"Started watching config file: {self.config_path}")

    def stop(self) -> None:
        """Stop watching config file"""
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()
            logger.info("Stopped config watcher")

    def is_running(self) -> bool:
        """Check if watcher is running"""
        return self._observer is not None and self._observer.is_alive()

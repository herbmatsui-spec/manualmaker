"""
Performance Optimization & Caching Module (Step 17)
Provides memory & disk caching for processing results to avoid redundant API calls.
"""

import logging
import hashlib
import json
from pathlib import Path
from typing import Optional, Any, Dict

from collections import OrderedDict

logger = logging.getLogger(__name__)

_DEFAULT_MAX_MEMORY_ENTRIES = 100


class CacheManager:
    """Cache manager for OCR and Gemini processing results"""

    def __init__(self, cache_dir: Optional[Path] = None, max_memory_entries: int = _DEFAULT_MAX_MEMORY_ENTRIES):
        self.cache_dir = cache_dir or Path("./temp/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: OrderedDict[str, Any] = OrderedDict()
        self._max_entries = max_memory_entries

    def _compute_key(self, content: str) -> str:
        """Compute SHA256 hash key for given content string"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if memory cache exceeds limit"""
        while len(self._memory_cache) > self._max_entries:
            evicted_key, _ = self._memory_cache.popitem(last=False)
            logger.debug(f"CacheManager: Evicted key {evicted_key[:8]} from memory cache")

    def get(self, content: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached result from memory or disk"""
        key = self._compute_key(content)
        if key in self._memory_cache:
            self._memory_cache.move_to_end(key)
            logger.debug(f"CacheManager: Memory hit for key {key[:8]}")
            return self._memory_cache[key]

        disk_path = self.cache_dir / f"{key}.json"
        if disk_path.exists():
            try:
                with open(disk_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._memory_cache[key] = data
                    self._evict_if_needed()
                    logger.debug(f"CacheManager: Disk hit for key {key[:8]}")
                    return data
            except Exception as e:
                logger.warning(f"CacheManager: Failed reading cache file {disk_path.name}: {e}")

        return None

    def set(self, content: str, result: Dict[str, Any]) -> None:
        """Store result in memory and disk cache"""
        key = self._compute_key(content)
        self._memory_cache[key] = result
        self._memory_cache.move_to_end(key)
        self._evict_if_needed()

        disk_path = self.cache_dir / f"{key}.json"
        try:
            with open(disk_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"CacheManager: Failed writing cache file {disk_path.name}: {e}")

    def clear(self) -> None:
        """Clear memory cache"""
        self._memory_cache.clear()

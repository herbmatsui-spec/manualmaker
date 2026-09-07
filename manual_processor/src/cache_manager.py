"""
Performance Optimization & Caching Module (Step 17)
Provides memory & disk caching for processing results to avoid redundant API calls.
"""

import logging
import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Any, Dict, Tuple

from collections import OrderedDict

logger = logging.getLogger(__name__)

_DEFAULT_MAX_MEMORY_ENTRIES = 100
_DEFAULT_TTL_SECONDS = 3600


class CacheManager:
    """Cache manager for OCR and Gemini processing results with TTL support"""

    def __init__(self, cache_dir: Optional[Path] = None, max_memory_entries: int = _DEFAULT_MAX_MEMORY_ENTRIES,
                 ttl_seconds: int = _DEFAULT_TTL_SECONDS):
        self.cache_dir = cache_dir or Path("./temp/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_entries = max_memory_entries
        self._ttl_seconds = ttl_seconds

    def _compute_key(self, content: str) -> str:
        """Compute SHA256 hash key for given content string"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _is_entry_expired(self, entry: Dict[str, Any]) -> bool:
        """Check if a cache entry has expired"""
        if "timestamp" not in entry:
            return False
        age = time.time() - entry["timestamp"]
        return age > self._ttl_seconds

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if memory cache exceeds limit"""
        while len(self._memory_cache) > self._max_entries:
            evicted_key, _ = self._memory_cache.popitem(last=False)
            logger.debug(f"CacheManager: Evicted key {evicted_key[:8]} from memory cache")

    def get(self, content: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached result from memory or disk"""
        key = self._compute_key(content)
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if self._is_entry_expired(entry):
                del self._memory_cache[key]
                logger.debug(f"CacheManager: Memory entry expired for key {key[:8]}")
            else:
                self._memory_cache.move_to_end(key)
                logger.debug(f"CacheManager: Memory hit for key {key[:8]}")
                return entry.get("data")

        disk_path = self.cache_dir / f"{key}.json"
        if disk_path.exists():
            try:
                with open(disk_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    entry = {"data": data, "timestamp": time.time()}
                    if self._is_entry_expired(entry):
                        disk_path.unlink(missing_ok=True)
                        logger.debug(f"CacheManager: Disk entry expired for key {key[:8]}")
                    else:
                        self._memory_cache[key] = entry
                        self._evict_if_needed()
                        logger.debug(f"CacheManager: Disk hit for key {key[:8]}")
                        return data
            except Exception as e:
                logger.warning(f"CacheManager: Failed reading cache file {disk_path.name}: {e}")

        return None

    def set(self, content: str, result: Dict[str, Any]) -> None:
        """Store result in memory and disk cache"""
        key = self._compute_key(content)
        entry = {"data": result, "timestamp": time.time()}
        self._memory_cache[key] = entry
        self._memory_cache.move_to_end(key)
        self._evict_if_needed()

        disk_path = self.cache_dir / f"{key}.json"
        try:
            with open(disk_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"CacheManager: Failed writing cache file {disk_path.name}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_entries = len(self._memory_cache)
        expired_count = sum(1 for e in self._memory_cache.values() if self._is_entry_expired(e))
        return {
            "total_entries": total_entries,
            "max_entries": self._max_entries,
            "expired_entries": expired_count,
            "ttl_seconds": self._ttl_seconds,
            "disk_cache_dir": str(self.cache_dir)
        }

    def clear(self) -> None:
        """Clear memory cache"""
        self._memory_cache.clear()

    def clear_expired(self) -> int:
        """Clear expired entries and return count"""
        expired_keys = [
            k for k, v in self._memory_cache.items()
            if self._is_entry_expired(v)
        ]
        for k in expired_keys:
            del self._memory_cache[k]
        logger.info(f"CacheManager: Cleared {len(expired_keys)} expired entries")
        return len(expired_keys)

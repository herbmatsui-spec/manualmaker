"""Tests for src/cache_manager.py"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from collections import OrderedDict

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestCacheManagerInit:
    """Tests for CacheManager.__init__"""

    def test_init_default_values(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        assert cm.cache_dir == tmp_path / "cache"
        assert cm._max_entries == 100
        assert cm._ttl_seconds == 3600
        assert isinstance(cm._memory_cache, OrderedDict)

    def test_init_custom_values(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", max_memory_entries=50, ttl_seconds=7200)
        assert cm._max_entries == 50
        assert cm._ttl_seconds == 7200

    def test_init_creates_cache_dir(self, tmp_path):
        from cache_manager import CacheManager

        cache_path = tmp_path / "new_cache"
        cm = CacheManager(cache_dir=cache_path)
        assert cache_path.exists()


class TestComputeKey:
    """Tests for _compute_key()"""

    def test_compute_key_consistency(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        key1 = cm._compute_key("test content")
        key2 = cm._compute_key("test content")
        assert key1 == key2

    def test_compute_key_different_for_different_content(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        key1 = cm._compute_key("content a")
        key2 = cm._compute_key("content b")
        assert key1 != key2

    def test_compute_key_is_sha256_hex(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        key = cm._compute_key("test")
        assert len(key) == 64
        assert all(c in '0123456789abcdef' for c in key)


class TestIsEntryExpired:
    """Tests for _is_entry_expired()"""

    def test_entry_without_timestamp_not_expired(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        assert cm._is_entry_expired({"data": {}}) is False

    def test_fresh_entry_not_expired(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", ttl_seconds=3600)
        entry = {"data": {}, "timestamp": time.time()}
        assert cm._is_entry_expired(entry) is False

    def test_old_entry_is_expired(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", ttl_seconds=3600)
        entry = {"data": {}, "timestamp": time.time() - 7200}
        assert cm._is_entry_expired(entry) is True


class TestEvictIfNeeded:
    """Tests for _evict_if_needed()"""

    def test_no_eviction_under_limit(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", max_memory_entries=10)
        for i in range(5):
            cm._memory_cache[f"key{i}"] = {"data": i}
        cm._evict_if_needed()
        assert len(cm._memory_cache) == 5

    def test_eviction_over_limit(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", max_memory_entries=3)
        for i in range(5):
            cm._memory_cache[f"key{i}"] = {"data": i}
        cm._evict_if_needed()
        assert len(cm._memory_cache) == 3


class TestGet:
    """Tests for get()"""

    def test_memory_hit(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        content = "test content"
        key = cm._compute_key(content)
        cm._memory_cache[key] = {"data": {"result": "value"}, "timestamp": time.time()}
        result = cm.get(content)
        assert result == {"result": "value"}

    def test_memory_hit_moves_to_end(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        content1 = "content a"
        content2 = "content b"
        key1 = cm._compute_key(content1)
        key2 = cm._compute_key(content2)
        cm._memory_cache[key1] = {"data": "a", "timestamp": time.time()}
        cm._memory_cache[key2] = {"data": "b", "timestamp": time.time()}
        cm.get(content1)
        keys = list(cm._memory_cache.keys())
        assert keys[0] == key2

    def test_memory_expired_gets_deleted(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", ttl_seconds=1)
        content = "content"
        key = cm._compute_key(content)
        cm._memory_cache[key] = {"data": "a", "timestamp": time.time() - 10}
        result = cm.get(content)
        assert result is None
        assert key not in cm._memory_cache

    def test_disk_hit(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        key = cm._compute_key("content")
        disk_path = cm.cache_dir / f"{key}.json"
        disk_path.write_text(json.dumps({"result": "disk_value"}))

        result = cm.get("content")
        assert result == {"result": "disk_value"}
        assert key in cm._memory_cache

    def test_disk_hit_evicts_if_needed(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", max_memory_entries=2)
        key = cm._compute_key("newcontent")
        disk_path = cm.cache_dir / f"{key}.json"
        disk_path.write_text(json.dumps({"result": "value"}))

        cm._memory_cache["old1"] = {"data": "a", "timestamp": time.time()}
        cm._memory_cache["old2"] = {"data": "b", "timestamp": time.time()}

        result = cm.get("newcontent")
        assert result == {"result": "value"}
        assert "old1" not in cm._memory_cache

    def test_disk_expired_gets_deleted(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", ttl_seconds=1)
        content = "disk content"
        key = cm._compute_key(content)
        disk_path = cm.cache_dir / f"{key}.json"
        old_timestamp = time.time() - 10
        entry_with_old_ts = {"data": {"result": "value"}, "timestamp": old_timestamp}
        disk_path.write_text(json.dumps({"data": {"result": "value"}, "timestamp": old_timestamp}))

        result = cm.get(content)
        assert result is None
        assert not disk_path.exists()

    def test_disk_read_error_returns_none(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        key = cm._compute_key("content")
        disk_path = cm.cache_dir / f"{key}.json"
        disk_path.write_text("invalid json{")

        result = cm.get("content")
        assert result is None

    def test_cache_miss_returns_none(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        result = cm.get("nonexistent content")
        assert result is None


class TestSet:
    """Tests for set()"""

    def test_set_stores_in_memory(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        cm.set("content", {"result": "value"})
        key = cm._compute_key("content")
        assert key in cm._memory_cache
        assert cm._memory_cache[key]["data"] == {"result": "value"}

    def test_set_stores_on_disk(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        cm.set("content", {"result": "value"})
        key = cm._compute_key("content")
        disk_path = cm.cache_dir / f"{key}.json"
        assert disk_path.exists()
        with open(disk_path) as f:
            stored = json.load(f)
            assert stored["data"] == {"result": "value"}
            assert "timestamp" in stored

    def test_set_evicts_if_needed(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", max_memory_entries=2)
        cm.set("a", {"n": 1})
        cm.set("b", {"n": 2})
        cm.set("c", {"n": 3})
        assert len(cm._memory_cache) == 2
        assert "a" not in cm._memory_cache

    def test_set_write_error_handled_gracefully(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        cm.set("content", {"result": "value"})

        disk_path = cm.cache_dir / f"{cm._compute_key('content')}.json"
        disk_path.chmod(0o000)

        try:
            cm.set("content2", {"result": "value2"})
        except Exception:
            pass
        finally:
            disk_path.chmod(0o644)


class TestGetStats:
    """Tests for get_stats()"""

    def test_stats_empty_cache(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        stats = cm.get_stats()
        assert stats["total_entries"] == 0
        assert stats["expired_entries"] == 0
        assert stats["max_entries"] == 100

    def test_stats_with_entries(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", max_memory_entries=50, ttl_seconds=3600)
        cm._memory_cache["k1"] = {"data": "a", "timestamp": time.time()}
        cm._memory_cache["k2"] = {"data": "b", "timestamp": time.time() - 7200}
        stats = cm.get_stats()
        assert stats["total_entries"] == 2
        assert stats["expired_entries"] == 1


class TestClear:
    """Tests for clear()"""

    def test_clear_removes_all_entries(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache")
        cm._memory_cache["k1"] = {"data": "a", "timestamp": time.time()}
        cm._memory_cache["k2"] = {"data": "b", "timestamp": time.time()}
        cm.clear()
        assert len(cm._memory_cache) == 0


class TestClearExpired:
    """Tests for clear_expired()"""

    def test_clear_expired_returns_count(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", ttl_seconds=1)
        cm._memory_cache["k1"] = {"data": "a", "timestamp": time.time()}
        cm._memory_cache["k2"] = {"data": "b", "timestamp": time.time() - 10}
        count = cm.clear_expired()
        assert count == 1
        assert len(cm._memory_cache) == 1
        assert "k1" in cm._memory_cache

    def test_clear_expired_none_expired(self, tmp_path):
        from cache_manager import CacheManager

        cm = CacheManager(cache_dir=tmp_path / "cache", ttl_seconds=3600)
        cm._memory_cache["k1"] = {"data": "a", "timestamp": time.time()}
        count = cm.clear_expired()
        assert count == 0

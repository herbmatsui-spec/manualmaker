"""Tests for src/prompt_engine/prompt_cache.py"""

import sys
from pathlib import Path

src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.prompt_engine.prompt_cache import (
    PromptCache,
    CachedPrompt,
    get_prompt_cache,
)


class TestPromptCache:
    def test_init_defaults(self):
        c = PromptCache()
        assert c._max_size == 100
        assert c._cache == {}
        assert c._hits == 0
        assert c._misses == 0

    def test_compute_hash_is_deterministic(self):
        c = PromptCache()
        h1 = c._compute_hash("horizontal", ["a", "b"], True, False, "ja")
        h2 = c._compute_hash("horizontal", ["a", "b"], True, False, "ja")
        assert h1 == h2
        assert len(h1) == 32

    def test_compute_hash_domain_terms_order_independent(self):
        c = PromptCache()
        h1 = c._compute_hash("h", ["a", "b"], True, False, "ja")
        h2 = c._compute_hash("h", ["b", "a"], True, False, "ja")
        assert h1 == h2

    def test_compute_hash_differs_when_inputs_differ(self):
        c = PromptCache()
        h1 = c._compute_hash("h", [], True, False, "ja")
        h2 = c._compute_hash("v", [], True, False, "ja")
        assert h1 != h2

    def test_miss_then_hit(self):
        c = PromptCache()
        assert c.get("h", [], True, False, "ja") is None
        c.put("h", [], True, False, "ja", "P")
        assert c.get("h", [], True, False, "ja") == "P"
        assert c._hits == 1
        assert c._misses == 1

    def test_put_evicts_oldest_when_full(self):
        c = PromptCache(max_size=2)
        c.put("a", [], True, False, "ja", "p1")
        c.put("b", [], True, False, "ja", "p2")
        c.put("c", [], True, False, "ja", "p3")
        assert len(c._cache) == 2
        assert c.get("a", [], True, False, "ja") is None
        assert c.get("b", [], True, False, "ja") == "p2"
        assert c.get("c", [], True, False, "ja") == "p3"

    def test_clear(self):
        c = PromptCache()
        c.put("h", [], True, False, "ja", "p")
        c.get("h", [], True, False, "ja")
        assert len(c._cache) == 1
        c.clear()
        assert c._cache == {}
        assert c._hits == 0
        assert c._misses == 0

    def test_stats_empty(self):
        c = PromptCache()
        stats = c.get_stats()
        assert stats["size"] == 0
        assert stats["max_size"] == 100
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate_percent"] == 0

    def test_stats_after_operations(self):
        c = PromptCache()
        c.put("h", [], True, False, "ja", "p")
        c.get("h", [], True, False, "ja")  # hit
        c.get("x", [], True, False, "ja")  # miss
        stats = c.get_stats()
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_percent"] == 50.0

    def test_cachedprompt_dataclass(self):
        cp = CachedPrompt(prompt="x", config_hash="abc", created_at=1.0)
        assert cp.prompt == "x"
        assert cp.config_hash == "abc"
        assert cp.created_at == 1.0

    def test_get_prompt_cache_singleton(self):
        # Reset module-level singleton for isolation
        import src.prompt_engine.prompt_cache as mod
        mod._global_cache = None
        a = get_prompt_cache()
        b = get_prompt_cache()
        assert a is b
        mod._global_cache = None

    def test_get_with_none_inputs(self):
        c = PromptCache()
        # All None / falsy should still produce a stable hash
        c.put(None, None, False, False, None, "PROMPT")
        assert c.get(None, None, False, False, None) == "PROMPT"
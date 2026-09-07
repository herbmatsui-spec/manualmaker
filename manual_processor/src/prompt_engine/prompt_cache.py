"""
Prompt Cache Module
Caches prompt builder results for repeated use
"""

import hashlib
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CachedPrompt:
    """Cached prompt entry"""
    prompt: str
    config_hash: str
    created_at: float


class PromptCache:
    """Simple in-memory cache for prompt builder results"""

    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, CachedPrompt] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def _compute_hash(self, layout: str, domain_terms: list, has_diagrams: bool,
                      low_quality: bool, language: str) -> str:
        """Compute a hash of the configuration parameters"""
        key_parts = [
            layout or "",
            ",".join(sorted(domain_terms or [])),
            str(has_diagrams),
            str(low_quality),
            language or "ja",
        ]
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, layout: str, domain_terms: list, has_diagrams: bool,
            low_quality: bool, language: str) -> Optional[str]:
        """
        Retrieve cached prompt if available

        Args:
            layout: Text layout direction
            domain_terms: List of domain terms
            has_diagrams: Whether diagrams are present
            low_quality: Whether low quality mode is enabled
            language: Language code

        Returns:
            Cached prompt string or None
        """
        config_hash = self._compute_hash(layout, domain_terms, has_diagrams, low_quality, language)

        if config_hash in self._cache:
            self._hits += 1
            logger.debug(f"Prompt cache HIT (hash={config_hash[:8]})")
            return self._cache[config_hash].prompt

        self._misses += 1
        logger.debug(f"Prompt cache MISS (hash={config_hash[:8]})")
        return None

    def put(self, layout: str, domain_terms: list, has_diagrams: bool,
            low_quality: bool, language: str, prompt: str) -> None:
        """
        Store prompt in cache

        Args:
            layout: Text layout direction
            domain_terms: List of domain terms
            has_diagrams: Whether diagrams are present
            low_quality: Whether low quality mode is enabled
            language: Language code
            prompt: The prompt string to cache
        """
        if len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"Prompt cache evicted oldest entry")

        config_hash = self._compute_hash(layout, domain_terms, has_diagrams, low_quality, language)
        self._cache[config_hash] = CachedPrompt(
            prompt=prompt,
            config_hash=config_hash,
            created_at=__import__("time").time()
        )
        logger.debug(f"Prompt cached (hash={config_hash[:8]})")

    def clear(self) -> None:
        """Clear all cached prompts"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Prompt cache cleared")

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(hit_rate, 2),
        }


_global_cache: Optional[PromptCache] = None


def get_prompt_cache() -> PromptCache:
    """Get the global prompt cache instance"""
    global _global_cache
    if _global_cache is None:
        _global_cache = PromptCache()
    return _global_cache

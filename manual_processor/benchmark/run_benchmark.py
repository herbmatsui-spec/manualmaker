#!/usr/bin/env python3
"""
Benchmark Runner for Manual Processor
Measures performance of OCR, Gemini API, and caching operations.
"""

import time
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, asdict
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class BenchmarkResult:
    """Result of a single benchmark operation"""
    name: str
    duration_seconds: float
    iterations: int
    avg_ms: float
    min_ms: float
    max_ms: float
    metadata: Dict[str, Any]


class BenchmarkRunner:
    """Runner for executing and collecting benchmark results"""

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    def run(self, name: str, func, iterations: int = 10, **metadata) -> BenchmarkResult:
        """
        Run a benchmark function multiple times.

        Args:
            name: Benchmark name
            func: Function to benchmark (no arguments)
            iterations: Number of iterations
            **metadata: Additional metadata to store

        Returns:
            BenchmarkResult
        """
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                func()
            except Exception as e:
                print(f"  Warning: Benchmark iteration failed: {e}")
            end = time.perf_counter()
            times.append((end - start) * 1000)

        if not times:
            times = [0]

        result = BenchmarkResult(
            name=name,
            duration_seconds=sum(times) / 1000,
            iterations=iterations,
            avg_ms=statistics.mean(times),
            min_ms=min(times),
            max_ms=max(times),
            metadata=metadata
        )
        self.results.append(result)
        return result

    def print_summary(self) -> None:
        """Print benchmark summary to console"""
        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)
        print(f"{'Name':<30} {'Avg (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12}")
        print("-" * 70)

        for r in self.results:
            print(f"{r.name:<30} {r.avg_ms:<12.2f} {r.min_ms:<12.2f} {r.max_ms:<12.2f}")

        print("=" * 70)

    def to_dict(self) -> List[Dict[str, Any]]:
        """Convert results to list of dicts"""
        return [asdict(r) for r in self.results]

    def save_json(self, output_path: Path) -> None:
        """Save results to JSON file"""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": time.time(),
                "results": self.to_dict()
            }, f, indent=2, ensure_ascii=False)


def benchmark_cache_operations():
    """Benchmark cache get/set operations"""
    from src.cache_manager import CacheManager
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        cache = CacheManager(cache_dir=Path(tmpdir))
        test_content = "Test content for caching benchmark " * 100
        test_data = {"summary": "test", "key_points": ["a", "b", "c"]}

        cache.set(test_content, test_data)
        for _ in range(100):
            cache.get(test_content)


def benchmark_text_chunking():
    """Benchmark text chunking operations"""
    from src.gemini_processor import GeminiProcessor
    import os

    try:
        processor = GeminiProcessor(api_key=os.getenv("GEMINI_API_KEY", "test"))
        long_text = "これはテストテキストです。 " * 500
        processor._chunk_text(long_text, max_tokens=4000)
    except Exception:
        pass


def benchmark_pii_masking():
    """Benchmark PII masking operations"""
    from src.security_manager import SecurityManager

    text = """
    連絡先: 090-1234-5678, メール: test@example.com
    住所: 〒123-4567 東京都渋谷区
    IPアドレス: 192.168.1.1
    クレジットカード: 4111-1111-1111-1111
    会社名: Example Corp.
    """ * 10

    for _ in range(50):
        SecurityManager.mask_sensitive_data(text)


def benchmark_language_detection():
    """Benchmark language detection"""
    from src.i18n_manager import I18nManager

    i18n = I18nManager()
    texts = [
        "これは日本語のテキストです",
        "This is English text for testing",
        "这是中文文本这是中文文本",
        "이것은 한국어 텍스트입니다",
        "Este es un texto en español",
    ]

    for _ in range(100):
        for text in texts:
            i18n.detect_language(text)


def benchmark_template_loading():
    """Benchmark template loading"""
    from src.pdf_generator import TemplateLoader

    TemplateLoader.clear_cache()
    for _ in range(50):
        TemplateLoader.load_template("compact")
        TemplateLoader.load_template("default")


def run_all_benchmarks():
    """Run all benchmarks and save results"""
    runner = BenchmarkRunner()

    print("Running benchmarks...")
    print("-" * 50)

    print("\n1. Cache Operations...")
    r = runner.run("cache_operations", benchmark_cache_operations, iterations=10)
    print(f"   Avg: {r.avg_ms:.2f}ms")

    print("\n2. Text Chunking...")
    r = runner.run("text_chunking", benchmark_text_chunking, iterations=5)
    print(f"   Avg: {r.avg_ms:.2f}ms")

    print("\n3. PII Masking...")
    r = runner.run("pii_masking", benchmark_pii_masking, iterations=10)
    print(f"   Avg: {r.avg_ms:.2f}ms")

    print("\n4. Language Detection...")
    r = runner.run("language_detection", benchmark_language_detection, iterations=10)
    print(f"   Avg: {r.avg_ms:.2f}ms")

    print("\n5. Template Loading...")
    r = runner.run("template_loading", benchmark_template_loading, iterations=20)
    print(f"   Avg: {r.avg_ms:.2f}ms")

    runner.print_summary()

    output_path = Path(__file__).parent / "benchmark_results.json"
    runner.save_json(output_path)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    run_all_benchmarks()

"""
Benchmark Suite (Step 23)
Measures execution performance of text processing and prompt generation.
"""

import time
import logging
from pathlib import Path
import tempfile
from src.text_processor import clean_extracted_text, normalize_japanese_text, combine_ocr_results, OCRResult
from src.security_manager import SecurityManager
from src.prompt_engine import HandwrittenPromptBuilder, PromptConfig
from src.cache_manager import CacheManager

logger = logging.getLogger(__name__)


def run_benchmark():
    print("=== Running Manual Processor Benchmark Suite ===")
    sample_text = "手書きテストテキスト   全角　文字  090-1234-5678 " * 1000

    t0 = time.time()
    for _ in range(50):
        clean_extracted_text(sample_text)
    t1 = time.time()
    print(f"1. clean_extracted_text (50 iterations): {t1 - t0:.4f}s")

    t0 = time.time()
    for _ in range(50):
        normalize_japanese_text(sample_text)
    t1 = time.time()
    print(f"2. normalize_japanese_text (50 iterations): {t1 - t0:.4f}s")

    t0 = time.time()
    for _ in range(50):
        SecurityManager.mask_sensitive_data(sample_text)
    t1 = time.time()
    print(f"3. mask_sensitive_data (50 iterations): {t1 - t0:.4f}s")

    t0 = time.time()
    for _ in range(100):
        builder = HandwrittenPromptBuilder()
        builder.build_handwritten_transcription_prompt(
            layout="vertical",
            domain_terms=["売上", "利益", "原価", "仕入", "在庫"],
            has_diagrams=True,
            low_quality=True
        )
    t1 = time.time()
    print(f"4. build_handwritten_transcription_prompt (100 iterations): {t1 - t0:.4f}s")

    with tempfile.TemporaryDirectory() as cache_dir:
        cache = CacheManager(cache_dir=Path(cache_dir))
        cached_builder = HandwrittenPromptBuilder(cache_manager=cache)
        options = {
            "layout": "vertical",
            "domain_terms": ["売上", "利益", "原価", "仕入", "在庫"],
            "has_diagrams": True,
            "low_quality": True,
        }
        t0 = time.time()
        for _ in range(100):
            cached_builder.build_handwritten_transcription_prompt(**options)
        t1 = time.time()
        print(f"5. cached prompt generation (100 iterations): {t1 - t0:.4f}s")

    from src.prompt_engine.handlers import RubyHandler, NoiseHandler, LayoutHandler
    ruby = RubyHandler()
    noise = NoiseHandler()
    layout = LayoutHandler()

    test_text = "日に本ほん\n売上総利益\n────\n仕入原価\n開始 → 処理 → 完了"

    t0 = time.time()
    for _ in range(100):
        ruby.post_process_text(test_text)
        noise.remove_noise_from_text(test_text)
        layout.detect_layout(test_text)
    t1 = time.time()
    print(f"6. handlers combined (100 iterations): {t1 - t0:.4f}s")

    print("=== Benchmark Completed Successfully ===")


if __name__ == "__main__":
    run_benchmark()

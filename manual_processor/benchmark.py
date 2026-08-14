"""
Benchmark Suite (Step 23)
Measures execution performance of text processing and cleanup.
"""

import time
import logging
from src.text_processor import clean_extracted_text, normalize_japanese_text, combine_ocr_results, OCRResult
from src.security_manager import SecurityManager

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

    print("=== Benchmark Completed Successfully ===")

if __name__ == "__main__":
    run_benchmark()

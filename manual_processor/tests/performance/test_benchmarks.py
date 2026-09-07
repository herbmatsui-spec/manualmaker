"""
Performance benchmarks for Manual Processor.
Measures execution time for critical operations.
"""

import time
import pytest
from pathlib import Path

from src.utils.validators import validate_pdf_content, validate_uuid, validate_filename
from src.security_manager import SecurityManager
from config.loader import load_settings
from tests.fixtures.sample_pdfs import create_sample_pdf


class TestValidationPerformance:
    """Benchmark validation functions"""

    def test_pdf_validation_performance(self, benchmark):
        """Benchmark PDF content validation"""
        pdf_data = create_sample_pdf(num_pages=1)
        
        def validate():
            assert validate_pdf_content(pdf_data) is True
        
        benchmark(validate)

    def test_uuid_validation_performance(self, benchmark):
        """Benchmark UUID validation"""
        uuid_str = "12345678-1234-1234-1234-123456789012"
        
        def validate():
            assert validate_uuid(uuid_str) is True
        
        benchmark(validate)

    def test_filename_validation_performance(self, benchmark):
        """Benchmark filename validation"""
        
        def validate():
            assert validate_filename("test_document_v2.pdf") is True
        
        benchmark(validate)


class TestPIIMaskingPerformance:
    """Benchmark PII masking operations"""

    def test_simple_text_masking(self, benchmark):
        """Benchmark masking simple text"""
        text = "Contact: user@example.com, Phone: 03-1234-5678"
        
        def mask():
            masked, _ = SecurityManager.mask_sensitive_data(text)
            assert "[REDACTED_EMAIL]" in masked
        
        benchmark(mask)

    def test_complex_text_masking(self, benchmark):
        """Benchmark masking complex text with multiple PII"""
        text = """
        User: John Doe
        Email: john.doe@example.com
        Phone: 03-1234-5678
        Card: 4111-1111-1111-1111
        My Number: 1234-5678-9012
        IP: 192.168.1.1
        """
        
        def mask():
            masked, info = SecurityManager.mask_sensitive_data(text)
            assert len(info["counts"]) >= 5
        
        benchmark(mask)

    def test_empty_text_masking(self, benchmark):
        """Benchmark masking empty text"""
        
        def mask():
            masked, _ = SecurityManager.mask_sensitive_data("")
            assert masked == ""
        
        benchmark(mask)


class TestConfigPerformance:
    """Benchmark configuration loading"""

    def test_config_loading_performance(self, benchmark):
        """Benchmark configuration loading"""
        
        def load():
            settings = load_settings()
            assert settings.app.name == "manual-processor"
        
        benchmark(load)

    def test_config_singleton_access(self, benchmark):
        """Benchmark config singleton access"""
        from config.config import Config
        
        # Ensure singleton is initialized
        Config.get_instance()
        
        def access():
            config = Config.get_instance()
            assert config.gemini_model_name is not None
        
        benchmark(access)


class TestPDFGenerationPerformance:
    """Benchmark PDF-related operations"""

    def test_pdf_creation_performance(self, benchmark):
        """Benchmark creating sample PDFs"""
        
        def create():
            pdf = create_sample_pdf(num_pages=1)
            assert len(pdf) > 0
            assert pdf.startswith(b"%PDF-")
        
        benchmark(create)

    def test_multipage_pdf_creation(self, benchmark):
        """Benchmark creating multi-page PDFs"""
        
        def create():
            pdf = create_sample_pdf(num_pages=10)
            assert len(pdf) > 0
        
        benchmark(create)


class TestBatchOperations:
    """Benchmark batch operations"""

    def test_batch_validation(self, benchmark):
        """Benchmark batch validation of multiple files"""
        
        def batch_validate():
            for i in range(100):
                pdf = create_sample_pdf(num_pages=1)
                assert validate_pdf_content(pdf) is True
        
        benchmark(batch_validate)

    def test_batch_uuid_generation(self, benchmark):
        """Benchmark batch UUID validation"""
        
        def batch_validate():
            for i in range(1000):
                uuid = f"{i:032d}"
                assert validate_uuid(uuid) is True
        
        benchmark(batch_validate)


class TestMemoryUsage:
    """Test memory usage for large operations"""

    def test_large_pdf_memory(self):
        """Test memory usage with large PDF (not a strict benchmark, just a check)"""
        import tracemalloc
        
        tracemalloc.start()
        
        # Create and process large PDF
        large_pdf = create_sample_pdf(num_pages=100)
        assert validate_pdf_content(large_pdf) is True
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Just verify it doesn't crash and memory is reasonable
        assert peak < 100 * 1024 * 1024  # Less than 100MB

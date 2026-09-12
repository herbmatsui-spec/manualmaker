"""
End-to-end integration tests for Manual Processor
Tests the complete PDF → processing → output pipeline
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processor.processor import DocumentProcessor
from config.config import Config
from src.gemini_processor import GeminiResult, Section


class TestIntegration:
    """Integration tests for the full processing pipeline"""

    @pytest.fixture
    def config(self):
        """Create a test configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config.get_instance()
            config._settings.paths.output_directory = str(Path(tmpdir) / "output")
            config._settings.paths.temp_directory = str(Path(tmpdir) / "temp")
            config._settings.processing.processor_type = "local"
            config._settings.gemini.model = "gemini-1.5-flash"
            config.ensure_directories()
            yield config

    @pytest.fixture
    def sample_pdf(self):
        """Create a simple test PDF"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b"%PDF-1.4\n%Test PDF content")
            return Path(f.name)

    @pytest.fixture
    def mock_api_keys(self):
        """Mock API keys for testing"""
        with patch.dict('os.environ', {
            'GEMINI_API_KEY': 'test_gemini_key',
            'GOOGLE_API_KEY': 'test_google_key',
            'GOOGLE_CLOUD_PROJECT_ID': 'test_project'
        }):
            yield

    def test_config_initialization(self, config):
        """Test that configuration initializes correctly"""
        assert config.output_directory.exists()
        assert config.temp_directory.exists()
        assert config.processor_type == "local"

    def test_document_processor_creation(self, config, mock_api_keys):
        """Test DocumentProcessor instantiation"""
        processor = DocumentProcessor(config)
        assert processor is not None
        assert processor.config == config

    @patch('src.processor.processor.ProcessorFactory')
    @patch('src.processor.processor.DiagramGenerator')
    @patch('src.pdf_processor.extract_images_from_pdf')
    @patch('src.processor.processor.OCRProcessor')
    def test_process_pdf_mocked(self, mock_ocr, mock_extract_images, mock_diagram, mock_factory, config, sample_pdf, mock_api_keys):
        """Test full PDF processing pipeline with mocked external services"""
        # Mock PDF image extraction - return a list with one mock image
        mock_img = Mock()
        mock_img.page_id = 1
        mock_extract_images.return_value = [mock_img]

        # Mock OCR processor
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text.return_value = "Sample extracted text from PDF"
        mock_ocr.return_value = mock_ocr_instance

        # Mock summarizer
        mock_summarizer = Mock()
        mock_summarizer.process_document.return_value = GeminiResult(
            title="Test Manual",
            summary="This is a test summary",
            key_points=["Point 1", "Point 2"],
            sections=[Section(title="Section 1", content="Content 1")],
            glossary=[{"term": "Term 1", "explanation": "Explanation 1"}]
        )
        mock_factory.create_processor.return_value = mock_summarizer

        # Mock diagram generator
        mock_diagram_instance = Mock()
        mock_diagram_instance.generate = Mock(return_value={})
        mock_diagram.return_value = mock_diagram_instance

        processor = DocumentProcessor(config)
        file_id = "test_file_123"
        
        result = processor.process_pdf(
            sample_pdf,
            compact_layout=False,
            use_emojis=False,
            file_id=file_id,
            base_url="http://localhost:8000"
        )

        # Verify result structure
        assert result is not None
        assert "title" in result
        assert "summary" in result
        assert "key_points" in result
        assert "sections" in result
        assert "glossary" in result
        assert "output_files" in result
        assert result["title"] == "Test Manual"

    def test_prompt_engine_integration(self, config):
        """Test prompt engine integration"""
        from src.prompt_engine.prompt_builder import HandwrittenPromptBuilder
        
        builder = HandwrittenPromptBuilder()
        prompt = builder.build_handwritten_transcription_prompt(
            layout="horizontal",
            domain_terms=["test", "manual"],
            has_diagrams=False,
            low_quality=False
        )
        
        assert prompt is not None
        assert len(prompt) > 100
        assert "一字一句" in prompt or "literal" in prompt.lower()

    def test_security_integration(self, config):
        """Test security manager integration with PII masking"""
        from src.security_manager import SecurityManager
        
        text = "Contact: test@example.com, Phone: 090-1234-5678"
        masked, info = SecurityManager.mask_sensitive_data(text, record_positions=True)
        
        assert "[REDACTED_EMAIL]" in masked
        assert "[REDACTED_PHONE]" in masked
        assert info["counts"]["EMAIL"] == 1
        # Phone pattern in Japanese is PHONE_JP
        assert info["counts"].get("PHONE_JP", 0) == 1

    def test_i18n_integration(self, config):
        """Test i18n manager integration"""
        from src.i18n_manager import I18nManager
        
        i18n = I18nManager(default_lang="ja")
        assert i18n.get_text("app_title") == "手書きマニュアル自動整理システム"
        
        i18n.set_language("en")
        assert i18n.get_text("app_title") == "Handwritten Manual Automated Processing System"
        
        langs = i18n.get_available_languages()
        assert "ja" in langs
        assert "en" in langs
        assert "zh" in langs
        assert "ko" in langs
        assert "es" in langs

    def test_template_system_integration(self, config):
        """Test template system integration"""
        from src.pdf_generator import TemplateLoader, create_formatted_pdf
        
        template = TemplateLoader.load_template("default")
        assert template["name"] == "default"
        
        resolved = TemplateLoader.resolve_template(template)
        assert "sections_order" in resolved
        
        is_valid, error = TemplateLoader.validate_template(resolved)
        assert is_valid is True

    def test_cache_integration(self, config):
        """Test cache manager integration"""
        from src.cache_manager import CacheManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(cache_dir=Path(tmpdir), max_memory_entries=10, ttl_seconds=60)
            
            test_content = "Test content for caching"
            test_data = {"result": "test data"}
            
            cache.set(test_content, test_data)
            retrieved = cache.get(test_content)
            
            assert retrieved == test_data
            
            stats = cache.get_stats()
            assert stats["total_entries"] == 1
            assert stats["expired_entries"] == 0

    def test_error_handling_integration(self, config):
        """Test error handling integration"""
        from src.exceptions import (
            OCRError, GeminiAPIError, TTSError, 
            TemplateNotFoundError, EncryptionError,
            USBDeviceError, I18nTranslationError
        )
        
        # Verify all exception types exist and can be raised
        for exc_class in [OCRError, GeminiAPIError, TTSError, 
                         TemplateNotFoundError, EncryptionError,
                         USBDeviceError, I18nTranslationError]:
            try:
                raise exc_class("Test error")
            except exc_class as e:
                assert str(e) == "Test error"
                assert e.error_code is not None


class TestWebAPIIntegration:
    """Integration tests for Web API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        from src.web.app import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_config_endpoint(self, client):
        """Test config endpoint"""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "gemini_model_name" in data
        assert "processor_type" in data

    def test_i18n_endpoints(self, client):
        """Test i18n endpoints"""
        # List languages
        response = client.get("/api/i18n/languages")
        assert response.status_code == 200
        data = response.json()
        assert "languages" in data
        assert "current" in data

        # Set language - using Pydantic model
        from src.web.app import SetLanguageRequest
        request_data = {"language": "en"}
        response = client.post("/api/i18n/set", json=request_data)
        assert response.status_code == 200
        assert response.json()["language"] == "en"

        # Get translations
        response = client.get("/api/i18n/translations/en")
        assert response.status_code == 200
        data = response.json()
        assert "app_title" in data

        # Detect language
        response = client.post("/api/i18n/detect", json={"text": "This is English"})
        assert response.status_code == 200
        data = response.json()
        assert "detected_language" in data

    def test_security_endpoints(self, client):
        """Test security endpoints"""
        # Security status
        response = client.get("/api/security/status")
        assert response.status_code == 200
        data = response.json()
        assert "pii_masking_enabled" in data

        # Mask text
        response = client.post("/api/security/mask", json={
            "text": "Email: test@example.com, Phone: 090-1234-5678"
        })
        assert response.status_code == 200
        data = response.json()
        assert "masked_text" in data
        assert "counts" in data

        # Audit logs
        response = client.get("/api/security/audit")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "count" in data

    def test_mermaid_endpoints(self, client):
        """Test mermaid endpoints"""
        # Validate mermaid
        response = client.post("/api/mermaid/validate", json={
            "mermaid_code": "graph TD; A-->B;"
        })
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data

    def test_upload_validation(self, client):
        """Test file upload validation"""
        # Test invalid file type
        files = {"file": ("test.txt", b"not a pdf", "text/plain")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 400


class TestErrorScenarios:
    """Test error handling and edge cases"""

    def test_invalid_file_processing(self):
        """Test processing non-existent file"""
        from config.config import Config
        from src.processor.processor import DocumentProcessor
        
        config = Config.get_instance()
        with patch('src.processor.processor.DiagramGenerator') as mock_diag:
            processor = DocumentProcessor(config)
            
            with pytest.raises(FileNotFoundError):
                processor.process_pdf(
                    Path("/nonexistent/file.pdf"),
                    file_id="test",
                    base_url="http://localhost:8000"
                )

    def test_invalid_template(self):
        """Test loading invalid template"""
        from src.pdf_generator import TemplateLoader, TemplateLoadError
        
        with pytest.raises(TemplateLoadError):
            TemplateLoader.load_template("nonexistent")

    def test_config_validation(self):
        """Test configuration validation"""
        config = Config.get_instance()
        errors = config.validate()
        # Should have no errors with proper config
        assert isinstance(errors, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
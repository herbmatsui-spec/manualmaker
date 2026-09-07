"""
Tests for processor_factory module (Step 16)
Target coverage: 95%
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.processor.processor_factory import (
    ProcessorFactory,
    LocalProcessor,
    HybridProcessor,
)
from src.gemini_processor import GeminiProcessor, GeminiResult, Section


class TestLocalProcessor:
    """Test LocalProcessor class"""

    def test_init_with_config(self):
        config = Mock()
        proc = LocalProcessor(config)
        assert proc.config is config

    def test_init_without_config(self):
        proc = LocalProcessor()
        assert proc.config is None

    def test_process_document_empty_text(self):
        proc = LocalProcessor()
        result = proc.process_document("")
        assert result.summary == ""
        assert result.key_points == []

    def test_process_document_whitespace_only(self):
        proc = LocalProcessor()
        result = proc.process_document("   \n\t  ")
        assert result.summary == ""
        assert result.key_points == []

    def test_process_document_single_line(self):
        proc = LocalProcessor()
        result = proc.process_document("Single line content")
        assert result.summary == "Single line content"
        assert result.key_points == ["Single line content"]
        assert result.difficulty_level == "beginner"

    def test_process_document_multiple_lines(self):
        proc = LocalProcessor()
        text = "First line\nSecond line\nThird line\nFourth line\nFifth line\nSixth line"
        result = proc.process_document(text)
        assert result.summary == "First line"
        assert len(result.key_points) == 5
        assert "Second line" in result.key_points

    def test_process_document_custom_audience(self):
        proc = LocalProcessor()
        result = proc.process_document("Test content", target_audience="expert")
        assert result.difficulty_level == "expert"

    def test_process_document_sections_created(self):
        proc = LocalProcessor()
        result = proc.process_document("Overview\nPoint 1\nPoint 2\nPoint 3")
        assert len(result.sections) == 2
        assert result.title == "ローカル要約マニュアル"


class TestHybridProcessor:
    """Test HybridProcessor class"""

    def test_init(self):
        gemini = Mock(spec=GeminiProcessor)
        local = Mock(spec=LocalProcessor)
        hybrid = HybridProcessor(gemini, local)
        assert hybrid.gemini is gemini
        assert hybrid.local is local

    def test_process_document_success(self):
        gemini = Mock(spec=GeminiProcessor)
        expected_result = GeminiResult(
            summary="gemini result",
            key_points=["point1"],
            sections=[Section(title="Test", content="test")],
            difficulty_level="beginner",
        )
        gemini.process_document.return_value = expected_result

        local = Mock(spec=LocalProcessor)
        hybrid = HybridProcessor(gemini, local)

        result = hybrid.process_document("test text")
        assert result.summary == "gemini result"
        gemini.process_document.assert_called_once()

    def test_process_document_fallback_on_exception(self):
        gemini = Mock(spec=GeminiProcessor)
        gemini.process_document.side_effect = Exception("API Error")

        local = Mock(spec=LocalProcessor)
        fallback_result = GeminiResult(
            summary="local fallback",
            key_points=["fallback"],
            sections=[],
            difficulty_level="beginner",
        )
        local.process_document.return_value = fallback_result

        hybrid = HybridProcessor(gemini, local)
        result = hybrid.process_document("test text")

        assert result.summary == "local fallback"
        local.process_document.assert_called_once()


class TestProcessorFactory:
    """Test ProcessorFactory class"""

    @patch("src.processor.processor_factory.GeminiProcessor")
    def test_create_processor_local_type(self, mock_gemini):
        config = Mock()
        config.processor_type = "local"
        config.fallback_enabled = True

        proc = ProcessorFactory.create_processor(config)
        assert isinstance(proc, LocalProcessor)

    @patch("src.processor.processor_factory.HandwrittenPromptBuilder")
    @patch("src.processor.processor_factory.GeminiProcessor")
    def test_create_processor_gemini_direct(self, mock_gemini_class, mock_builder):
        mock_gemini = Mock(spec=GeminiProcessor)
        mock_gemini_class.return_value = mock_gemini
        mock_builder.from_config.return_value = Mock()

        config = Mock()
        config.processor_type = "gemini"
        config.gemini_api_key = "test_key"
        config.gemini_model_name = "gemini-1.5-flash"
        config.gemini_temperature = 0.3
        config.gemini_max_output_tokens = 2048
        config.fallback_enabled = False

        proc = ProcessorFactory.create_processor(config)
        assert proc is mock_gemini

    @patch("src.processor.processor_factory.HandwrittenPromptBuilder")
    @patch("src.processor.processor_factory.GeminiProcessor")
    def test_create_processor_hybrid(self, mock_gemini_class, mock_builder):
        mock_gemini = Mock(spec=GeminiProcessor)
        mock_gemini_class.return_value = mock_gemini
        mock_builder.from_config.return_value = Mock()

        config = Mock()
        config.processor_type = "hybrid"
        config.gemini_api_key = "test_key"
        config.gemini_model_name = "gemini-1.5-flash"
        config.gemini_temperature = 0.3
        config.gemini_max_output_tokens = 2048
        config.fallback_enabled = True

        proc = ProcessorFactory.create_processor(config)
        assert isinstance(proc, HybridProcessor)

    @patch("src.processor.processor_factory.HandwrittenPromptBuilder")
    @patch("src.processor.processor_factory.GeminiProcessor")
    def test_create_processor_gemini_with_fallback_enabled(self, mock_gemini_class, mock_builder):
        mock_gemini = Mock(spec=GeminiProcessor)
        mock_gemini_class.return_value = mock_gemini
        mock_builder.from_config.return_value = Mock()

        config = Mock()
        config.processor_type = "gemini"
        config.gemini_api_key = "test_key"
        config.gemini_model_name = "gemini-1.5-flash"
        config.gemini_temperature = 0.3
        config.gemini_max_output_tokens = 2048
        config.fallback_enabled = True

        proc = ProcessorFactory.create_processor(config)
        assert isinstance(proc, HybridProcessor)

    @patch("src.processor.processor_factory.GeminiProcessor")
    def test_create_processor_fallback_on_gemini_error(self, mock_gemini_class):
        mock_gemini_class.side_effect = Exception("Init failed")

        config = Mock()
        config.processor_type = "gemini"
        config.gemini_api_key = "bad_key"
        config.fallback_enabled = True

        proc = ProcessorFactory.create_processor(config)
        assert isinstance(proc, LocalProcessor)

    @patch("src.processor.processor_factory.GeminiProcessor")
    def test_create_processor_raises_when_fallback_disabled(self, mock_gemini_class):
        from src.exceptions import ProcessingError

        mock_gemini_class.side_effect = Exception("Init failed")

        config = Mock()
        config.processor_type = "gemini"
        config.gemini_api_key = "bad_key"
        config.fallback_enabled = False

        with pytest.raises(ProcessingError):
            ProcessorFactory.create_processor(config)

    @patch("src.processor.processor_factory.HandwrittenPromptBuilder")
    @patch("src.processor.processor_factory.GeminiProcessor")
    def test_create_processor_uses_google_api_key(self, mock_gemini_class, mock_builder):
        mock_gemini = Mock(spec=GeminiProcessor)
        mock_gemini_class.return_value = mock_gemini
        mock_builder.from_config.return_value = Mock()

        config = Mock()
        config.processor_type = "gemini"
        config.google_api_key = "google_key"
        config.gemini_api_key = None
        config.gemini_model_name = "gemini-1.5-flash"
        config.gemini_temperature = 0.3
        config.gemini_max_output_tokens = 2048
        config.fallback_enabled = False

        ProcessorFactory.create_processor(config)
        call_kwargs = mock_gemini_class.call_args[1]
        assert call_kwargs["api_key"] == "google_key"

    @patch("src.processor.processor_factory.GeminiProcessor")
    def test_create_processor_none_config_uses_defaults(self, mock_gemini_class):
        mock_gemini = Mock(spec=GeminiProcessor)
        mock_gemini_class.return_value = mock_gemini

        proc = ProcessorFactory.create_processor(config=None, processor_type="local")
        assert isinstance(proc, LocalProcessor)

    @patch("src.processor.processor_factory.GeminiProcessor")
    def test_create_processor_case_insensitive_type(self, mock_gemini_class):
        config = Mock()
        config.processor_type = "LOCAL"
        config.fallback_enabled = True

        proc = ProcessorFactory.create_processor(config)
        assert isinstance(proc, LocalProcessor)

    @patch("src.processor.processor_factory.GeminiProcessor")
    def test_create_processor_logs_correct_type(self, mock_gemini_class, caplog):
        import logging
        caplog.set_level(logging.INFO)

        config = Mock()
        config.processor_type = "local"
        config.fallback_enabled = True

        ProcessorFactory.create_processor(config)
        assert "local" in caplog.text.lower()

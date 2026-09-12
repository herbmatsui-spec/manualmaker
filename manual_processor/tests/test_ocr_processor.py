"""
Tests for ocr_processor module (Step 21)
Target coverage: 90%
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from PIL import Image
import io

from src.ocr_processor import (
    OCRProcessor,
    OCRResult,
    BoundingBox,
    perform_ocr_on_image,
    process_pdf_with_ocr,
)


class TestBoundingBox:
    """Test BoundingBox dataclass"""

    def test_init(self):
        bb = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0)
        assert bb.x == 10.0
        assert bb.y == 20.0
        assert bb.width == 100.0
        assert bb.height == 50.0


class TestOCRResult:
    """Test OCRResult dataclass"""

    def test_init_defaults(self):
        result = OCRResult(
            text="test text",
            confidence=0.95,
            page_number=1,
            bounding_boxes=[]
        )
        assert result.text == "test text"
        assert result.has_error is False
        assert result.error_message == ""

    def test_init_with_error(self):
        result = OCRResult(
            text="",
            confidence=0.0,
            page_number=1,
            bounding_boxes=[],
            has_error=True,
            error_message="Test error"
        )
        assert result.has_error is True
        assert result.error_message == "Test error"


class TestOCRProcessor:
    """Test OCRProcessor class"""

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', False)
    def test_init_raises_when_vision_not_available(self):
        with pytest.raises(Exception) as exc_info:
            OCRProcessor()
        assert "インストールされていません" in str(exc_info.value)

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    @patch('src.ocr_processor.vision.ImageAnnotatorClient')
    def test_init_with_credentials(self, mock_client):
        with patch.dict('os.environ', {'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds'}):
            processor = OCRProcessor()
            assert processor.client is not None
            mock_client.assert_called_once()

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    @patch('src.ocr_processor.vision.ImageAnnotatorClient')
    def test_init_with_api_key(self, mock_client):
        with patch.dict('os.environ', {}, clear=True):
            processor = OCRProcessor(api_key="test_api_key")
            assert processor.client is not None

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    @patch('src.ocr_processor.vision.ImageAnnotatorClient')
    def test_init_with_env_api_key(self, mock_client):
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'env_api_key'}):
            processor = OCRProcessor()
            assert processor.client is not None

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    @patch('src.ocr_processor.vision.ImageAnnotatorClient')
    def test_init_client_init_error(self, mock_client):
        mock_client.side_effect = Exception("Init failed")
        processor = OCRProcessor()
        assert processor.client is None

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_extract_text_empty_image(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()
        processor.prompt_builder = None
        processor.post_process_text = Mock(return_value="")

        mock_response = Mock()
        mock_response.text = ""
        mock_response.full_text_annotation = None

        with patch.object(processor, 'perform_ocr_on_image', return_value=OCRResult(text="", confidence=0.0, page_number=1, bounding_boxes=[])):
            result = processor.extract_text(Mock())
            assert result == ""

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_extract_text_with_content(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()
        processor.prompt_builder = None
        processor.post_process_text = Mock(return_value="cleaned text")

        ocr_result = OCRResult(text="raw text", confidence=0.9, page_number=1, bounding_boxes=[])

        with patch.object(processor, 'perform_ocr_on_image', return_value=ocr_result):
            result = processor.extract_text(Mock())
            assert result == "cleaned text"

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_build_transcription_prompt_no_builder(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.prompt_builder = None

        result = processor.build_transcription_prompt()
        assert result == ""

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_build_transcription_prompt_with_builder(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.prompt_builder = Mock()
        processor.prompt_builder.build_handwritten_transcription_prompt.return_value = "transcription prompt"

        result = processor.build_transcription_prompt()
        assert result == "transcription prompt"

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_post_process_text_empty(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.prompt_builder = None

        result = processor.post_process_text("")
        assert result == ""

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_post_process_text_no_builder(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.prompt_builder = None

        result = processor.post_process_text("some text")
        assert result == "some text"

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_is_service_available_false_when_no_client(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = None

        result = processor.is_service_available()
        assert result is False

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_is_service_available_true(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()

        mock_vision = Mock()
        mock_vision.Image.return_value = Mock()
        with patch('src.ocr_processor.vision', mock_vision):
            processor.is_service_available()
            processor.client.document_text_detection.assert_called_once()

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_is_service_available_exception(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()
        processor.client.document_text_detection.side_effect = Exception("API Error")

        result = processor.is_service_available()
        assert result is False

    def test_image_to_bytes(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        image = Image.new('RGB', (100, 100), color='red')

        result = processor._image_to_bytes(image)

        assert isinstance(result, bytes)
        assert len(result) > 0

        img = Image.open(io.BytesIO(result))
        assert img.size == (100, 100)

    def test_vision_result_to_ocr_result_empty(self):
        from src.ocr_processor import OCRProcessor
        processor = OCRProcessor.__new__(OCRProcessor)

        mock_response = Mock()
        mock_response.full_text_annotation = None

        result = processor._vision_result_to_ocr_result(mock_response, page_number=1)

        assert result.text == ""
        assert result.confidence == 0.0
        assert result.page_number == 1

    def test_vision_result_to_ocr_result_with_full_annotation(self):
        from src.ocr_processor import OCRProcessor
        processor = OCRProcessor.__new__(OCRProcessor)

        mock_symbol = Mock()
        mock_symbol.text = "a"

        mock_word = Mock()
        mock_word.symbols = [mock_symbol]
        mock_word.confidence = 0.95
        mock_word.bounding_box.vertices = [
            Mock(x=0, y=0), Mock(x=10, y=0), Mock(x=10, y=10), Mock(x=0, y=10)
        ]

        mock_paragraph = Mock()
        mock_paragraph.words = [mock_word]

        mock_block = Mock()
        mock_block.paragraphs = [mock_paragraph]

        mock_page = Mock()
        mock_page.blocks = [mock_block]

        mock_response = Mock()
        mock_response.full_text_annotation.pages = [mock_page]
        mock_response.full_text_annotation.text = "a"

        result = processor._vision_result_to_ocr_result(mock_response, page_number=1)

        assert result.text == "a"
        assert result.confidence == 0.95
        assert len(result.bounding_boxes) == 1


class TestPerformOCROnImage:
    """Test perform_ocr_on_image convenience function"""

    @patch('src.ocr_processor.OCRProcessor')
    def test_calls_processor_method(self, mock_processor_class):
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor

        image = Image.new('RGB', (100, 100))
        perform_ocr_on_image(image, language_hints=['ja'])

        mock_processor.perform_ocr_on_image.assert_called_once()


class TestProcessPdfWithOCR:
    """Test process_pdf_with_ocr convenience function"""

    @patch('src.ocr_processor.OCRProcessor')
    def test_calls_processor_method(self, mock_processor_class):
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor

        images = [Image.new('RGB', (100, 100))]
        process_pdf_with_ocr(images)

        mock_processor.process_pdf_pages.assert_called_once()


class TestCalculateOverallConfidence:
    """Test calculate_overall_confidence static method"""

    def test_empty_results(self):
        result = OCRProcessor.calculate_overall_confidence([])
        assert result == 0.0

    def test_single_result(self):
        results = [
            OCRResult(text="hello", confidence=0.9, page_number=1, bounding_boxes=[])
        ]
        assert OCRProcessor.calculate_overall_confidence(results) == 0.9

    def test_multiple_results_weighted(self):
        results = [
            OCRResult(text="hi", confidence=0.8, page_number=1, bounding_boxes=[]),
            OCRResult(text="hello world test", confidence=1.0, page_number=2, bounding_boxes=[]),
        ]
        result = OCRProcessor.calculate_overall_confidence(results)
        expected = (0.8 * 2 + 1.0 * 16) / 18
        assert abs(result - expected) < 0.001

    def test_results_with_empty_text(self):
        results = [
            OCRResult(text="", confidence=0.9, page_number=1, bounding_boxes=[]),
            OCRResult(text="content", confidence=0.5, page_number=2, bounding_boxes=[]),
        ]
        result = OCRProcessor.calculate_overall_confidence(results)
        expected = (0.9 * 1 + 0.5 * 7) / 8
        assert abs(result - expected) < 0.001


class TestOCRProcessorPerformOcr:
    """Test OCRProcessor.perform_ocr_on_image method"""

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_client_none_raises_ocr_error(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = None

        with pytest.raises(Exception) as exc_info:
            processor.perform_ocr_on_image(Image.new('RGB', (10, 10)))
        assert "初期化されていません" in str(exc_info.value)

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_success_path(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()
        processor.timeout = 30
        processor.prompt_builder = None

        mock_response = Mock()
        mock_response.error.message = ""
        mock_response.full_text_annotation = None
        processor.client.document_text_detection.return_value = mock_response

        image = Image.new('RGB', (10, 10))
        result = processor.perform_ocr_on_image(image)

        assert result.text == ""
        assert result.page_number == 1
        processor.client.document_text_detection.assert_called_once()

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_success_with_language_hints(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()
        processor.timeout = 30
        processor.prompt_builder = None

        mock_response = Mock()
        mock_response.error.message = ""
        mock_response.full_text_annotation = None
        processor.client.document_text_detection.return_value = mock_response

        processor.perform_ocr_on_image(Image.new('RGB', (10, 10)), language_hints=['en'])
        kwargs = processor.client.document_text_detection.call_args.kwargs
        assert kwargs["image_context"].language_hints == ['en']

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_api_error_message_raises(self):
        import src.ocr_processor as ocr_mod
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()
        processor.timeout = 30
        processor.prompt_builder = None

        mock_response = Mock()
        mock_response.error.message = "quota exceeded"
        processor.client.document_text_detection.return_value = mock_response

        with pytest.raises(ocr_mod.OCRError) as exc_info:
            processor.perform_ocr_on_image(Image.new('RGB', (10, 10)))
        assert "Vision APIエラー" in str(exc_info.value)

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_google_api_call_error(self):
        import src.ocr_processor as ocr_mod
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()
        processor.timeout = 30
        processor.prompt_builder = None
        processor.client.document_text_detection.side_effect = ocr_mod.GoogleAPICallError("api down")

        with pytest.raises(ocr_mod.OCRError) as exc_info:
            processor.perform_ocr_on_image(Image.new('RGB', (10, 10)))
        assert "OCR API呼び出しに失敗しました" in str(exc_info.value)

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_retry_error(self):
        # RetryError は GoogleAPICallError のサブクラスのため、
        # モジュール名をパッチして except RetryError 経路を分離する
        class FakeRetryError(Exception):
            pass

        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()
        processor.timeout = 30
        processor.prompt_builder = None
        processor.client.document_text_detection.side_effect = FakeRetryError("retry failed")

        import src.ocr_processor as ocr_mod
        with patch('src.ocr_processor.RetryError', FakeRetryError):
            with pytest.raises(ocr_mod.OCRError) as exc_info:
                processor.perform_ocr_on_image(Image.new('RGB', (10, 10)))
        assert "タイムアウトしました" in str(exc_info.value)

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_deadline_exceeded(self):
        # DeadlineExceeded は GoogleAPICallError のサブクラスのため、
        # モジュール名をパッチして except DeadlineExceeded 経路を分離する
        class FakeDeadlineExceeded(Exception):
            pass

        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()
        processor.timeout = 30
        processor.prompt_builder = None
        processor.client.document_text_detection.side_effect = FakeDeadlineExceeded("deadline")

        import src.ocr_processor as ocr_mod
        with patch('src.ocr_processor.DeadlineExceeded', FakeDeadlineExceeded):
            with pytest.raises(ocr_mod.OCRError) as exc_info:
                processor.perform_ocr_on_image(Image.new('RGB', (10, 10)))
        assert "タイムアウトしました" in str(exc_info.value)

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_unexpected_error(self):
        import src.ocr_processor as ocr_mod
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()
        processor.timeout = 30
        processor.prompt_builder = None
        processor.client.document_text_detection.side_effect = RuntimeError("boom")

        with pytest.raises(ocr_mod.OCRError) as exc_info:
            processor.perform_ocr_on_image(Image.new('RGB', (10, 10)))
        assert "OCR処理に失敗しました" in str(exc_info.value)


class TestOCRProcessorPostProcess:
    """Test post_process_text with prompt_builder (handler pathway)"""

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_post_process_with_builder(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.prompt_builder = Mock()

        result = processor.post_process_text("手順 ①：ボタンを押す ※注記")
        assert isinstance(result, str)

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_extract_text_with_builder(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.client = Mock()
        processor.prompt_builder = Mock()

        ocr_result = OCRResult(text="raw テキスト", confidence=0.9, page_number=1, bounding_boxes=[])
        with patch.object(processor, 'perform_ocr_on_image', return_value=ocr_result):
            result = processor.extract_text(Mock())
        assert isinstance(result, str)


class TestOCRProcessorProcessPdfPages:
    """Test OCRProcessor.process_pdf_pages method"""

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_success_multiple_pages(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.prompt_builder = None

        def fake_ocr(image, language_hints=None):
            return OCRResult(text="page", confidence=0.9, page_number=1, bounding_boxes=[])

        with patch.object(processor, 'perform_ocr_on_image', side_effect=fake_ocr):
            results = processor.process_pdf_pages([Mock(), Mock(), Mock()])

        assert len(results) == 3
        assert [r.page_number for r in results] == [1, 2, 3]
        for r in results:
            assert r.has_error is False

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_progress_callback_called(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.prompt_builder = None

        progress_calls = []

        def fake_ocr(image, language_hints=None):
            return OCRResult(text="x", confidence=0.9, page_number=1, bounding_boxes=[])

        with patch.object(processor, 'perform_ocr_on_image', side_effect=fake_ocr):
            processor.process_pdf_pages(
                [Mock(), Mock()],
                progress_callback=lambda current, total: progress_calls.append((current, total))
            )

        assert progress_calls == [(1, 2), (2, 2)]

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_progress_callback_error_swallowed(self, caplog):
        import logging
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.prompt_builder = None

        def bad_callback(current, total):
            raise RuntimeError("callback failed")

        def fake_ocr(image, language_hints=None):
            return OCRResult(text="x", confidence=0.9, page_number=1, bounding_boxes=[])

        with caplog.at_level(logging.WARNING):
            with patch.object(processor, 'perform_ocr_on_image', side_effect=fake_ocr):
                results = processor.process_pdf_pages([Mock()], progress_callback=bad_callback)

        assert len(results) == 1
        assert any("進捗コールバックエラー" in r.message for r in caplog.records)

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_page_failure_recorded_as_error_result(self):
        import src.ocr_processor as ocr_mod
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.prompt_builder = None

        calls = {"n": 0}

        def fake_ocr(image, language_hints=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ocr_mod.OCRError("page 1 failed")
            return OCRResult(text="ok", confidence=0.9, page_number=1, bounding_boxes=[])

        with patch.object(processor, 'perform_ocr_on_image', side_effect=fake_ocr):
            results = processor.process_pdf_pages([Mock(), Mock()])

        assert len(results) == 2
        assert results[0].has_error is True
        assert "page 1 failed" in results[0].error_message
        assert results[0].page_number == 1
        assert results[1].has_error is False
        assert results[1].page_number == 2

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_cancel_token_stops_processing(self):
        class CancelToken:
            def __init__(self, cancel_on_page):
                self.cancel_on_page = cancel_on_page
                self.calls = 0

            def throw_if_cancelled(self):
                self.calls += 1
                if self.calls >= self.cancel_on_page:
                    raise RuntimeError("cancelled")

        processor = OCRProcessor.__new__(OCRProcessor)
        processor.prompt_builder = None

        token = CancelToken(cancel_on_page=2)

        def fake_ocr(image, language_hints=None):
            return OCRResult(text="x", confidence=0.9, page_number=1, bounding_boxes=[])

        with patch.object(processor, 'perform_ocr_on_image', side_effect=fake_ocr):
            with pytest.raises(RuntimeError, match="cancelled"):
                processor.process_pdf_pages([Mock(), Mock(), Mock()], cancel_token=token)

        assert token.calls == 2

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    def test_cancel_token_without_method_ignored(self):
        processor = OCRProcessor.__new__(OCRProcessor)
        processor.prompt_builder = None

        def fake_ocr(image, language_hints=None):
            return OCRResult(text="x", confidence=0.9, page_number=1, bounding_boxes=[])

        with patch.object(processor, 'perform_ocr_on_image', side_effect=fake_ocr):
            results = processor.process_pdf_pages([Mock()], cancel_token=object())

        assert len(results) == 1


class TestOCRProcessorInitEdgeCases:
    """Test __init__ edge cases"""

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    @patch('src.ocr_processor.vision.ImageAnnotatorClient')
    def test_init_with_credentials_path_sets_env(self, mock_client):
        with patch.dict('os.environ', {}, clear=True):
            OCRProcessor(credentials_path="/custom/path.json")
            import os
            assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == "/custom/path.json"

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    @patch('src.ocr_processor.vision.ImageAnnotatorClient')
    def test_init_with_gemini_api_key_env(self, mock_client):
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'gemini_key'}, clear=True):
            processor = OCRProcessor()
            assert processor.client is not None

    @patch('src.ocr_processor._HAS_GOOGLE_VISION', True)
    @patch('src.ocr_processor.vision.ImageAnnotatorClient')
    def test_init_with_prompt_builder_and_project(self, mock_client):
        builder = Mock()
        processor = OCRProcessor(project_id="my-project", prompt_builder=builder)
        assert processor.project_id == "my-project"
        assert processor.prompt_builder is builder


class TestModuleImportFallback:
    """Test module-level ImportError fallback (lines 15-20)"""

    def test_google_vision_import_fallback(self):
        import importlib
        import sys
        import src.ocr_processor as ocr_mod

        saved = {name: mod for name, mod in sys.modules.items()
                 if name == "google" or name.startswith("google.")}
        for name in saved:
            del sys.modules[name]
        sys.modules["google"] = None  # force ImportError on 'from google.cloud import ...'
        try:
            importlib.reload(ocr_mod)
            assert ocr_mod._HAS_GOOGLE_VISION is False
            assert ocr_mod.vision is None
            assert ocr_mod.GoogleAPICallError is Exception
            assert ocr_mod.RetryError is Exception
            assert ocr_mod.DeadlineExceeded is Exception
        finally:
            del sys.modules["google"]
            sys.modules.update(saved)
            importlib.reload(ocr_mod)

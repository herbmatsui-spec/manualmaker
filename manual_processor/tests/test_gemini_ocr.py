"""Tests for GeminiOCRProcessor (src/gemini_ocr.py)"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class TestGeminiOCRProcessor:
    """GeminiOCRProcessor covers both google.genai and legacy google.generativeai branches."""

    def test_init_uses_genai_new_client(self):
        from src.gemini_ocr import GeminiOCRProcessor

        with patch("src.gemini_ocr._HAS_GENAI", True), \
             patch("src.gemini_ocr.genai") as genai_mod:
            genai_mod.Client = MagicMock(return_value=MagicMock())
            proc = GeminiOCRProcessor(api_key="K")
        genai_mod.Client.assert_called_once_with(api_key="K")
        assert proc.model_name == "gemini-1.5-flash"

    def test_init_uses_legacy_generativeai(self):
        from src.gemini_ocr import GeminiOCRProcessor

        with patch("src.gemini_ocr._HAS_GENAI", False), \
             patch("src.gemini_ocr.genai") as genai_mod:
            genai_mod.GenerativeModel = MagicMock(return_value=MagicMock())
            proc = GeminiOCRProcessor(api_key="K")
        genai_mod.configure.assert_called_once_with(api_key="K")
        genai_mod.GenerativeModel.assert_called_once_with("gemini-1.5-flash")

    def test_extract_text_new_genai_success(self):
        from src.gemini_ocr import GeminiOCRProcessor

        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = _FakeResponse("hello")

        with patch("src.gemini_ocr._HAS_GENAI", True), \
             patch("src.gemini_ocr.genai") as genai_mod:
            genai_mod.Client = MagicMock(return_value=fake_client)
            proc = GeminiOCRProcessor(api_key="K")
            image = MagicMock()
            text = proc.extract_text(image)

        assert text == "hello"
        fake_client.models.generate_content.assert_called_once()

    def test_extract_text_returns_empty_when_no_text(self):
        from src.gemini_ocr import GeminiOCRProcessor

        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = _FakeResponse(None)

        with patch("src.gemini_ocr._HAS_GENAI", True), \
             patch("src.gemini_ocr.genai") as genai_mod:
            genai_mod.Client = MagicMock(return_value=fake_client)
            proc = GeminiOCRProcessor(api_key="K")
            text = proc.extract_text(MagicMock())

        assert text == ""

    def test_extract_text_wraps_exception_in_OCRError(self):
        from src.exceptions import OCRError
        from src.gemini_ocr import GeminiOCRProcessor

        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = RuntimeError("boom")

        with patch("src.gemini_ocr._HAS_GENAI", True), \
             patch("src.gemini_ocr.genai") as genai_mod:
            genai_mod.Client = MagicMock(return_value=fake_client)
            proc = GeminiOCRProcessor(api_key="K")
            with pytest.raises(OCRError):
                proc.extract_text(MagicMock())

    def test_extract_text_legacy_genai_branch(self):
        from src.gemini_ocr import GeminiOCRProcessor

        legacy_model = MagicMock()
        legacy_model.generate_content.return_value = _FakeResponse("legacy-text")

        with patch("src.gemini_ocr._HAS_GENAI", False), \
             patch("src.gemini_ocr.genai") as genai_mod:
            genai_mod.GenerativeModel = MagicMock(return_value=legacy_model)
            proc = GeminiOCRProcessor(api_key="K")
            text = proc.extract_text(MagicMock())

        assert text == "legacy-text"

    def test_extract_text_from_pdf_page_success(self, monkeypatch):
        from src.gemini_ocr import GeminiOCRProcessor

        fake_image = MagicMock(name="PageImage")
        monkeypatch.setattr(
            "src.pdf_processor.extract_images_from_pdf",
            lambda pdf_path, dpi: [fake_image, fake_image],
        )

        with patch("src.gemini_ocr._HAS_GENAI", True), \
             patch("src.gemini_ocr.genai") as genai_mod:
            fake_client = MagicMock()
            fake_client.models.generate_content.return_value = _FakeResponse("page-text")
            genai_mod.Client = MagicMock(return_value=fake_client)
            proc = GeminiOCRProcessor(api_key="K")
            result = proc.extract_text_from_pdf_page(Path("dummy.pdf"), page_number=2)

        assert result == "page-text"

    def test_extract_text_from_pdf_page_invalid_page_number(self, monkeypatch):
        from src.exceptions import OCRError
        from src.gemini_ocr import GeminiOCRProcessor

        monkeypatch.setattr(
            "src.pdf_processor.extract_images_from_pdf",
            lambda pdf_path, dpi: [MagicMock()],
        )

        with patch("src.gemini_ocr._HAS_GENAI", True), \
             patch("src.gemini_ocr.genai") as genai_mod:
            genai_mod.Client = MagicMock(return_value=MagicMock())
            proc = GeminiOCRProcessor(api_key="K")
            with pytest.raises(OCRError):
                proc.extract_text_from_pdf_page(Path("dummy.pdf"), page_number=99)

    def test_extract_text_from_pdf_page_wraps_exception(self, monkeypatch):
        from src.exceptions import OCRError
        from src.gemini_ocr import GeminiOCRProcessor

        monkeypatch.setattr(
            "src.pdf_processor.extract_images_from_pdf",
            lambda pdf_path, dpi: (_ for _ in ()).throw(RuntimeError("pdf fail")),
        )

        with patch("src.gemini_ocr._HAS_GENAI", True), \
             patch("src.gemini_ocr.genai") as genai_mod:
            genai_mod.Client = MagicMock(return_value=MagicMock())
            proc = GeminiOCRProcessor(api_key="K")
            with pytest.raises(OCRError):
                proc.extract_text_from_pdf_page(Path("dummy.pdf"), page_number=1)
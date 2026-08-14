"""processor.py の部分失敗許容および並列処理のユニットテスト"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.exceptions import OCRError

def test_partial_ocr_failure():
    """1ページ失敗しても全体の処理が完了し、エラーページプレースホルダーが含まれること"""
    from src.processor.processor import DocumentProcessor
    from config.config import Config

    config = MagicMock(spec=Config)
    config.google_api_key = "dummy"
    config.gemini_api_key = "dummy"
    config.max_file_size_mb = 50
    config.supported_extensions = [".pdf"]
    config.pdf_dpi = 150

    processor = DocumentProcessor(config=config)
    processor.ocr_processor = MagicMock()

    # ページ1成功、ページ2例外送出
    def mock_extract(img):
        if getattr(img, "page_id", 0) == 2:
            raise OCRError("Page 2 failed")
        return "Page Text OK"

    processor.ocr_processor.extract_text.side_effect = mock_extract

    # fitz mock
    with patch("fitz.open") as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.page_count = 2
        mock_page1 = MagicMock()
        mock_page2 = MagicMock()
        
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"fake_png_data"
        mock_page1.get_pixmap.return_value = mock_pix
        mock_page2.get_pixmap.return_value = mock_pix
        
        mock_doc.load_page.side_effect = [mock_page1, mock_page2]
        mock_fitz.return_value.__enter__.return_value = mock_doc

        with patch("PIL.Image.open") as mock_img_open:
            img1 = MagicMock()
            img1.page_id = 1
            img2 = MagicMock()
            img2.page_id = 2
            mock_img_open.side_effect = [img1, img2]

            extracted = processor._extract_text_from_pdf(Path("dummy.pdf"))

            assert "Page Text OK" in extracted
            assert "[ページ 2: 読み取り失敗]" in extracted

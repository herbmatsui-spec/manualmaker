"""
Tests for PDF processor module.
"""

import io
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from PIL import Image

from src.pdf_processor import (
    extract_images_from_pdf,
    get_pdf_metadata,
    is_pdf_valid,
    process_pdf_with_progress,
)


class TestExtractImagesFromPdf:
    """Test PDF image extraction"""

    @patch('src.pdf_processor.pdfium.PdfDocument')
    def test_extract_images_success(self, mock_pdf_document):
        """Test successful image extraction from PDF"""
        # Create a real temp PDF file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            # Write minimal valid PDF
            f.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n")
            f.write(b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n")
            f.write(b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n")
            f.write(b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n")
            f.write(b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF\n")
            temp_path = Path(f.name)

        try:
            # Mock PdfDocument
            mock_doc = MagicMock()
            mock_doc.__len__ = Mock(return_value=1)
            
            # Create a mock page that returns a PIL Image
            mock_page = MagicMock()
            mock_img = Image.new('RGB', (100, 100))
            mock_render = MagicMock(return_value=MagicMock(to_pil=MagicMock(return_value=mock_img)))
            mock_page.render = mock_render
            
            mock_doc.__getitem__ = Mock(return_value=mock_page)
            mock_pdf_document.return_value = mock_doc
            
            images = extract_images_from_pdf(temp_path, dpi=150)
            assert len(images) == 1
            assert isinstance(images[0], Image.Image)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_extract_images_file_not_found(self):
        """Test extraction with non-existent file"""
        with pytest.raises(FileNotFoundError):
            extract_images_from_pdf(Path("/nonexistent/file.pdf"))

    @patch('src.pdf_processor.pdfium.PdfDocument')
    def test_extract_images_render_error(self, mock_pdf_document):
        """Test extraction when rendering fails"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b"%PDF-1.4\n")
            temp_path = Path(f.name)

        try:
            mock_doc = MagicMock()
            mock_doc.__len__ = Mock(return_value=1)
            mock_page = MagicMock()
            mock_page.render = Mock(side_effect=Exception("Render failed"))
            mock_doc.__getitem__ = Mock(return_value=mock_page)
            mock_pdf_document.return_value = mock_doc

            with pytest.raises(ValueError):
                extract_images_from_pdf(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)


class TestGetPdfMetadata:
    """Test PDF metadata extraction"""

    @patch('src.pdf_processor.PdfReader')
    def test_get_metadata_success(self, mock_pdf_reader):
        """Test successful metadata extraction"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b"%PDF-1.4\n")
            temp_path = Path(f.name)

        try:
            mock_reader = MagicMock()
            mock_meta = MagicMock()
            mock_meta.title = "Test Document"
            mock_meta.author = "Test Author"
            mock_meta.subject = "Test Subject"
            mock_meta.keywords = "test, pdf"
            mock_meta.creation_date = None
            mock_meta.modification_date = None
            mock_reader.metadata = mock_meta
            mock_reader.pages = [MagicMock()]
            mock_pdf_reader.return_value = mock_reader

            metadata = get_pdf_metadata(temp_path)
            assert metadata['title'] == "Test Document"
            assert metadata['author'] == "Test Author"
            assert metadata['page_count'] == 1
        finally:
            temp_path.unlink(missing_ok=True)

    def test_get_metadata_file_not_found(self):
        """Test metadata extraction with non-existent file"""
        metadata = get_pdf_metadata(Path("/nonexistent/file.pdf"))
        assert metadata['page_count'] == 0
        assert metadata['title'] == ''


class TestIsPdfValid:
    """Test PDF validation"""

    @patch('src.pdf_processor.PdfReader')
    def test_valid_pdf(self, mock_pdf_reader):
        """Test valid PDF validation"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b"%PDF-1.4\n")
            temp_path = Path(f.name)

        try:
            mock_reader = MagicMock()
            mock_reader.pages = [MagicMock(), MagicMock()]
            mock_pdf_reader.return_value = mock_reader

            assert is_pdf_valid(temp_path) is True
        finally:
            temp_path.unlink(missing_ok=True)

    def test_nonexistent_file(self):
        """Test validation of non-existent file"""
        assert is_pdf_valid(Path("/nonexistent/file.pdf")) is False

    def test_empty_file(self):
        """Test validation of empty file"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            temp_path = Path(f.name)

        try:
            assert is_pdf_valid(temp_path) is False
        finally:
            temp_path.unlink(missing_ok=True)


class TestProcessPdfWithProgress:
    """Test PDF processing with progress callbacks"""

    @patch('src.pdf_processor.pdfium.PdfDocument')
    def test_process_with_progress_success(self, mock_pdf_document):
        """Test successful PDF processing with progress"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b"%PDF-1.4\n")
            temp_path = Path(f.name)

        try:
            mock_doc = MagicMock()
            mock_doc.__len__ = Mock(return_value=2)
            
            mock_page = MagicMock()
            mock_img = Image.new('RGB', (100, 100))
            mock_render = MagicMock(return_value=MagicMock(to_pil=MagicMock(return_value=mock_img)))
            mock_page.render = mock_render
            
            mock_doc.__getitem__ = Mock(return_value=mock_page)
            mock_pdf_document.return_value = mock_doc

            progress_callback = Mock()
            images = process_pdf_with_progress(temp_path, progress_callback=progress_callback)

            assert len(images) == 2
            assert progress_callback.call_count == 2
            progress_callback.assert_any_call(1, 2)
            progress_callback.assert_any_call(2, 2)
        finally:
            temp_path.unlink(missing_ok=True)

    @patch('src.pdf_processor.pdfium.PdfDocument')
    def test_process_with_progress_callback_exception(self, mock_pdf_document):
        """Test progress callback exception handling"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b"%PDF-1.4\n")
            temp_path = Path(f.name)

        try:
            mock_doc = MagicMock()
            mock_doc.__len__ = Mock(return_value=1)
            
            mock_page = MagicMock()
            mock_img = Image.new('RGB', (100, 100))
            mock_render = MagicMock(return_value=MagicMock(to_pil=MagicMock(return_value=mock_img)))
            mock_page.render = mock_render
            
            mock_doc.__getitem__ = Mock(return_value=mock_page)
            mock_pdf_document.return_value = mock_doc

            # Callback that raises exception
            progress_callback = Mock(side_effect=Exception("Callback error"))

            # Should not raise, callback exception should be caught
            images = process_pdf_with_progress(temp_path, progress_callback=progress_callback)
            assert len(images) == 1
        finally:
            temp_path.unlink(missing_ok=True)

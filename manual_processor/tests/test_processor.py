"""
Tests for DocumentProcessor.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.processor.processor import DocumentProcessor, _sections_to_dicts
from src.models import Section
from src.exceptions import ProcessingError


class TestSectionsToDicts:
    """Test _sections_to_dicts helper function"""

    def test_convert_dict_sections(self):
        """Test converting dict sections"""
        sections = [
            {"title": "Section 1", "content": "Content 1"},
            {"title": "Section 2", "content": "Content 2"}
        ]
        result = _sections_to_dicts(sections)
        assert len(result) == 2
        assert result[0]["title"] == "Section 1"

    def test_convert_section_objects(self):
        """Test converting Section objects"""
        sections = [
            Section(title="Section 1", content="Content 1"),
            Section(title="Section 2", content="Content 2")
        ]
        result = _sections_to_dicts(sections)
        assert len(result) == 2
        assert result[0]["title"] == "Section 1"
        assert result[0]["content"] == "Content 1"

    def test_convert_mixed_types(self):
        """Test converting mixed section types"""
        sections = [
            {"title": "Dict Section", "content": "Content"},
            Section(title="Object Section", content="Content"),
            "String Section"
        ]
        result = _sections_to_dicts(sections)
        assert len(result) == 3
        assert result[2]["title"] == "String Section"
        assert result[2]["content"] == ""

    def test_convert_none(self):
        """Test converting None input"""
        result = _sections_to_dicts(None)
        assert result == []

    def test_convert_empty_list(self):
        """Test converting empty list"""
        result = _sections_to_dicts([])
        assert result == []


class TestDocumentProcessorInit:
    """Test DocumentProcessor initialization"""

    @patch('src.processor.processor.Config.get_instance')
    @patch('src.processor.processor.HandwrittenPromptBuilder.from_config')
    @patch('src.processor.processor.ProcessorFactory.create_processor')
    @patch('src.processor.processor.DiagramGenerator')
    @patch('src.processor.processor.OCRProcessor')
    def test_init_with_config(self, mock_ocr, mock_diagram, mock_factory, mock_prompt, mock_config):
        """Test initialization with config"""
        mock_config_instance = Mock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.google_api_key = ""
        mock_config_instance.gemini_model_name = "gemini-1.5-flash"
        mock_config_instance.summary_model = "gemini-1.5-flash"
        
        processor = DocumentProcessor(config=mock_config_instance)
        
        assert processor.config == mock_config_instance
        mock_ocr.assert_called_once()
        mock_factory.assert_called_once()
        mock_diagram.assert_called_once()

    @patch('src.processor.processor.Config.get_instance')
    def test_init_without_config(self, mock_config):
        """Test initialization without config (uses singleton)"""
        mock_config.return_value = Mock()
        
        with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
             patch('src.processor.processor.ProcessorFactory.create_processor'), \
             patch('src.processor.processor.DiagramGenerator'), \
             patch('src.processor.processor.OCRProcessor'):
            processor = DocumentProcessor()
            assert processor.config is not None


class TestDocumentProcessorProcessPdf:
    """Test DocumentProcessor.process_pdf method"""

    @patch('src.processor.processor.DocumentProcessor._extract_text_from_pdf')
    @patch('src.processor.processor.DocumentProcessor._run_summarization')
    @patch('src.processor.processor.DocumentProcessor._run_output_generation')
    def test_process_pdf_success(self, mock_output, mock_summarize, mock_extract):
        """Test successful PDF processing"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"
            mock_config_instance.pii_masking_enabled = False
            mock_config_instance.max_file_size_mb = 100
            mock_config_instance.supported_extensions = [".pdf"]
            
            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config_instance)
                
                # Mock the processing steps
                mock_extract.return_value = "extracted text"
                mock_summarize.return_value = Mock(
                    title="Title",
                    summary="Summary",
                    key_points=["Point 1"],
                    sections=[],
                    glossary=[]
                )
                mock_output.return_value = {"pdf": "output.pdf"}
                
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    temp_path = Path(f.name)
                
                try:
                    result = processor.process_pdf(temp_path)
                    assert result["success"] is True
                    mock_extract.assert_called_once()
                    mock_summarize.assert_called_once()
                    mock_output.assert_called_once()
                finally:
                    temp_path.unlink(missing_ok=True)

    def test_process_pdf_file_not_found(self):
        """Test processing non-existent PDF"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            
            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config_instance)
                
                # Should raise FileNotFoundError
                with pytest.raises(FileNotFoundError):
                    processor.process_pdf(Path("/nonexistent/file.pdf"))

    @patch('src.processor.processor.DocumentProcessor._extract_text_from_pdf')
    def test_process_pdf_extraction_exception(self, mock_extract):
        """Test processing when text extraction fails"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.max_file_size_mb = 100
            mock_config_instance.supported_extensions = [".pdf"]
            
            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config_instance)
                mock_extract.side_effect = Exception("Extraction failed")
                
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    temp_path = Path(f.name)
                
                try:
                    result = processor.process_pdf(temp_path)
                    assert result["success"] is False
                    assert "error" in result
                finally:
                    temp_path.unlink(missing_ok=True)


class TestDocumentProcessorOutputs:
    """Test output generation"""

    @patch('src.processor.processor.create_formatted_pdf')
    @patch('src.processor.processor.create_word_document')
    @patch('src.processor.processor.create_audio_summary')
    @patch('src.processor.processor.DiagramGenerator')
    def test_generate_outputs_success(self, mock_diagram_cls, mock_audio, mock_docx, mock_pdf):
        """Test successful output generation"""
        mock_config = Mock()
        mock_config.generate_diagram = False
        mock_config.output_directory = Path("./output")
        mock_config.gemini_model_name = "gemini-1.5-flash"
        
        mock_diagram = Mock()
        mock_diagram_cls.return_value = mock_diagram
        
        mock_pdf.return_value = "output.pdf"
        mock_docx.return_value = "output.docx"
        mock_audio.return_value = "output.mp3"
        
        with patch('src.processor.processor.Config.get_instance') as mock_config_get:
            mock_config_get.return_value = mock_config
            
            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config)
                
                summary_result = Mock()
                summary_result.title = "Test"
                summary_result.summary = "Summary"
                summary_result.key_points = []
                summary_result.sections = []
                summary_result.glossary = []
                
                result = processor._generate_outputs(
                    summary_result=summary_result,
                    pdf_path=Path("./test.pdf")
                )
                
                assert "pdf" in result
                assert "docx" in result

    def test_sections_to_dicts_integration(self):
        """Test _sections_to_dicts with various input types"""
        # This tests the helper function used by _generate_outputs
        sections = [
            {"title": "Dict", "content": "dict content"},
            Section(title="Object", content="object content")
        ]
        result = _sections_to_dicts(sections)
        assert len(result) == 2
        assert result[0]["title"] == "Dict"
        assert result[1]["title"] == "Object"

    @patch('src.processor.processor.create_formatted_pdf')
    @patch('src.processor.processor.create_word_document')
    @patch('src.processor.processor.create_audio_summary')
    @patch('src.processor.processor.DiagramGenerator')
    @patch('src.qr_generator.QRGenerator')
    def test_generate_outputs_with_qr(self, mock_qr_cls, mock_diagram_cls, mock_audio, mock_docx, mock_pdf):
        """Test QR code generation when file_id is provided"""
        import tempfile
        mock_config = Mock()
        mock_config.generate_diagram = False
        mock_config.output_directory = Path(tempfile.mkdtemp())
        mock_config.gemini_model_name = "gemini-1.5-flash"

        mock_diagram = Mock()
        mock_diagram_cls.return_value = mock_diagram

        mock_pdf.return_value = "output.pdf"
        mock_docx.return_value = "output.docx"

        # Pre-create the audio file at the path _generate_outputs will use
        audio_path = mock_config.output_directory / "test_Test.mp3"
        audio_path.write_bytes(b"fake mp3 content")
        mock_audio.return_value = audio_path

        mock_qr = Mock()
        mock_qr.generate_qr.return_value = mock_config.output_directory / "test_qr.png"
        mock_qr_cls.return_value = mock_qr

        with patch('src.processor.processor.Config.get_instance') as mock_config_get:
            mock_config_get.return_value = mock_config

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config)

                summary_result = Mock()
                summary_result.title = "Test"
                summary_result.summary = "Summary"
                summary_result.key_points = []
                summary_result.sections = []
                summary_result.glossary = []

                result = processor._generate_outputs(
                    summary_result=summary_result,
                    pdf_path=Path("./test.pdf"),
                    file_id="test-file-id-123",
                    base_url="http://localhost:8000"
                )

                assert "pdf" in result
                assert "docx" in result
                assert "qr" in result
                mock_qr.generate_qr.assert_called_once()
                # Verify QR URL contains the file_id
                qr_call_args = mock_qr.generate_qr.call_args
                assert "test-file-id-123" in qr_call_args[0][0]

    @patch('src.processor.processor.create_formatted_pdf')
    @patch('src.processor.processor.create_word_document')
    @patch('src.processor.processor.create_audio_summary')
    @patch('src.processor.processor.DiagramGenerator')
    def test_generate_outputs_without_qr_when_no_file_id(self, mock_diagram_cls, mock_audio, mock_docx, mock_pdf):
        """Test QR code is NOT generated when file_id is None"""
        mock_config = Mock()
        mock_config.generate_diagram = False
        mock_config.output_directory = Path("./output")
        mock_config.gemini_model_name = "gemini-1.5-flash"

        mock_diagram = Mock()
        mock_diagram_cls.return_value = mock_diagram

        mock_pdf.return_value = "output.pdf"
        mock_docx.return_value = "output.docx"
        mock_audio.return_value = "output.mp3"

        with patch('src.processor.processor.Config.get_instance') as mock_config_get:
            mock_config_get.return_value = mock_config

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config)

                summary_result = Mock()
                summary_result.title = "Test"
                summary_result.summary = "Summary"
                summary_result.key_points = []
                summary_result.sections = []
                summary_result.glossary = []

                result = processor._generate_outputs(
                    summary_result=summary_result,
                    pdf_path=Path("./test.pdf")
                )

                assert "pdf" in result
                assert "docx" in result
                assert "qr" not in result


class TestProcessPdfFileSizeLimit:
    """Test process_pdf file size limit exceeded (lines 74-82)"""

    @patch('src.processor.processor.DocumentProcessor._extract_text_from_pdf')
    def test_process_pdf_file_size_exceeded(self, mock_extract):
        """Test processing fails when file size exceeds limit"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.max_file_size_mb = 1
            mock_config_instance.supported_extensions = [".pdf"]
            mock_config_instance.pii_masking_enabled = False
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config_instance)

                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    f.write(b'\x00' * (2 * 1024 * 1024))
                    temp_path = Path(f.name)

                try:
                    result = processor.process_pdf(temp_path)
                    assert result["success"] is False
                    assert "ファイルサイズ" in result["error"]
                    assert "超えています" in result["error"]
                    mock_extract.assert_not_called()
                finally:
                    temp_path.unlink(missing_ok=True)


class TestProcessPdfUnsupportedExtension:
    """Test process_pdf unsupported extension (lines 84-91)"""

    def test_process_pdf_unsupported_extension(self):
        """Test processing fails for unsupported file extensions"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.max_file_size_mb = 100
            mock_config_instance.supported_extensions = [".pdf"]
            mock_config_instance.pii_masking_enabled = False
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config_instance)

                with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
                    temp_path = Path(f.name)

                try:
                    result = processor.process_pdf(temp_path)
                    assert result["success"] is False
                    assert "サポートされていないファイル形式" in result["error"]
                finally:
                    temp_path.unlink(missing_ok=True)


class TestProcessPdfPIIMasking:
    """Test process_pdf with PII masking enabled (lines 106-110)"""

    @patch('src.processor.processor.SecurityManager.mask_sensitive_data')
    @patch('src.processor.processor.DocumentProcessor._extract_text_from_pdf')
    @patch('src.processor.processor.DocumentProcessor._run_summarization')
    @patch('src.processor.processor.DocumentProcessor._run_output_generation')
    def test_process_pdf_with_pii_masking(self, mock_output, mock_summarize, mock_extract, mock_mask):
        """Test PII masking is applied when enabled"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.max_file_size_mb = 100
            mock_config_instance.supported_extensions = [".pdf"]
            mock_config_instance.pii_masking_enabled = True
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config_instance)

                mock_extract.return_value = "original text with sensitive data"
                mock_mask.return_value = ("masked text", {"counts": {"email": 2, "phone": 1}})
                mock_summarize.return_value = Mock(
                    title="Title",
                    summary="Summary",
                    key_points=["Point 1"],
                    sections=[],
                    glossary=[]
                )
                mock_output.return_value = {"pdf": "output.pdf"}

                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    temp_path = Path(f.name)

                try:
                    result = processor.process_pdf(temp_path)
                    assert result["success"] is True
                    mock_mask.assert_called_once_with("original text with sensitive data", record_positions=True)
                finally:
                    temp_path.unlink(missing_ok=True)


class TestRunSummarizationWithCancelToken:
    """Test _run_summarization with cancel_token parameter (lines 153-167)"""

    def test_run_summarization_with_cancel_token(self):
        """Test summarization with cancel_token parameter"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor') as mock_factory, \
                 patch('src.processor.processor.DiagramGenerator'), \
                 patch('src.processor.processor.OCRProcessor'):
                mock_summarizer = Mock()
                mock_summarizer.process_document = Mock(return_value=Mock(
                    title="Title",
                    summary="Summary",
                    key_points=["Point 1"]
                ))
                mock_factory.return_value = mock_summarizer

                processor = DocumentProcessor(config=mock_config_instance)

                mock_cancel_token = Mock()
                mock_cancel_token.throw_if_cancelled = Mock()

                def process_with_cancel(text, cancel_token=None):
                    cancel_token.throw_if_cancelled()
                    return Mock(title="Title", summary="Summary", key_points=["Point 1"])

                mock_summarizer.process_document = process_with_cancel

                result = processor._run_summarization(
                    "extracted text",
                    Path("./test.pdf"),
                    cancel_token=mock_cancel_token
                )

                mock_cancel_token.throw_if_cancelled.assert_called()


class TestProcessBatch:
    """Test process_batch method (lines 177-189)"""

    @patch('src.processor.processor.DocumentProcessor.process_pdf')
    def test_process_batch_success(self, mock_process):
        """Test batch processing of multiple PDFs"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config_instance)

                mock_process.return_value = {"success": True}

                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f1, \
                     tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f2, \
                     tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f3:

                    temp_pdf1 = Path(f1.name)
                    temp_pdf2 = Path(f2.name)
                    temp_txt = Path(f3.name)

                    try:
                        results = processor.process_batch([temp_pdf1, temp_pdf2, temp_txt])
                        assert len(results) == 2
                        assert mock_process.call_count == 2
                    finally:
                        temp_pdf1.unlink(missing_ok=True)
                        temp_pdf2.unlink(missing_ok=True)
                        temp_txt.unlink(missing_ok=True)

    @patch('src.processor.processor.DocumentProcessor.process_pdf')
    def test_process_batch_with_cancel(self, mock_process):
        """Test batch processing respects cancel token - exception propagates"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config_instance)

                mock_cancel = Mock()
                mock_cancel.throw_if_cancelled = Mock(side_effect=Exception("Cancelled"))

                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    temp_path = Path(f.name)

                    try:
                        with pytest.raises(Exception, match="Cancelled"):
                            processor.process_batch([temp_path], cancel_token=mock_cancel)
                    finally:
                        temp_path.unlink(missing_ok=True)


class TestProcessDirectory:
    """Test process_directory method (lines 191-201)"""

    @patch('src.processor.processor.DocumentProcessor.process_batch')
    def test_process_directory_success(self, mock_batch):
        """Test processing all PDFs in a directory"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config_instance)

                mock_batch.return_value = [{"success": True}]

                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir)
                    (tmp_path / "file1.pdf").write_bytes(b"pdf content 1")
                    (tmp_path / "file2.pdf").write_bytes(b"pdf content 2")
                    (tmp_path / "file3.txt").write_bytes(b"not a pdf")

                    results = processor.process_directory(tmp_path, recursive=True)
                    assert len(results) == 1
                    mock_batch.assert_called_once()

    def test_process_directory_not_found(self):
        """Test processing non-existent directory raises error"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config_instance)

                with pytest.raises(NotADirectoryError):
                    processor.process_directory(Path("/nonexistent/directory"))


class TestExtractTextFromPdfPartialFailure:
    """Test _extract_text_from_pdf partial failure paths (lines 213-282)"""

    @patch('src.processor.processor.OCRProcessor')
    @patch('src.pdf_processor.extract_images_from_pdf')
    def test_extract_text_partial_ocr_failure(self, mock_extract_images, mock_ocr_cls):
        """Test partial OCR failure is handled and logged"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"
            mock_config_instance.pdf_dpi = 150

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'):
                mock_ocr = Mock()
                mock_ocr_cls.return_value = mock_ocr

                mock_img1 = Mock()
                mock_img1.page_id = 1
                mock_img2 = Mock()
                mock_img2.page_id = 2
                mock_extract_images.return_value = [mock_img1, mock_img2]

                def ocr_side_effect(img):
                    if img.page_id == 1:
                        return "Page 1 text"
                    else:
                        raise Exception("OCR failed")

                mock_ocr.extract_text = ocr_side_effect

                processor = DocumentProcessor(config=mock_config_instance)

                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    temp_path = Path(f.name)

                try:
                    result = processor._extract_text_from_pdf(temp_path)
                    assert "Page 1 text" in result
                    assert "読み取り失敗" in result
                finally:
                    temp_path.unlink(missing_ok=True)

    @patch('src.processor.processor.OCRProcessor')
    @patch('src.pdf_processor.extract_images_from_pdf')
    def test_extract_text_fallback_to_fitz(self, mock_extract_images, mock_ocr_cls):
        """Test fallback to fitz when extract_images_from_pdf fails"""
        import io
        from PIL import Image

        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"
            mock_config_instance.pdf_dpi = 150

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'):
                mock_ocr = Mock()
                mock_ocr_cls.return_value = mock_ocr
                mock_ocr.extract_text = Mock(return_value="Extracted text from image")

                mock_extract_images.side_effect = FileNotFoundError("No images found")

                with patch('fitz.open') as mock_fitz_open, \
                     patch('fitz.Matrix') as mock_fitz_matrix, \
                     patch('PIL.Image.open') as mock_image_open:
                    mock_doc = Mock()
                    mock_doc.page_count = 1
                    mock_page = Mock()
                    mock_pix = Mock()
                    mock_pix.tobytes = Mock(return_value=b"png data")
                    mock_page.get_pixmap = Mock(return_value=mock_pix)
                    mock_doc.load_page = Mock(return_value=mock_page)
                    mock_fitz_open.return_value.__enter__ = Mock(return_value=mock_doc)
                    mock_fitz_open.return_value.__exit__ = Mock(return_value=False)
                    mock_fitz_matrix.return_value = Mock()

                    mock_img = Mock()
                    mock_img.page_id = 1
                    mock_image_open.return_value = mock_img

                    processor = DocumentProcessor(config=mock_config_instance)

                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                        temp_path = Path(f.name)

                    try:
                        result = processor._extract_text_from_pdf(temp_path)
                        assert "Extracted text from image" in result
                    finally:
                        temp_path.unlink(missing_ok=True)

    @patch('src.processor.processor.OCRProcessor')
    @patch('src.pdf_processor.extract_images_from_pdf')
    def test_extract_text_all_pages_fail(self, mock_extract_images, mock_ocr_cls):
        """Test exception raised when all OCR pages fail"""
        with patch('src.processor.processor.Config.get_instance') as mock_config:
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.google_api_key = ""
            mock_config_instance.gemini_model_name = "gemini-1.5-flash"
            mock_config_instance.summary_model = "gemini-1.5-flash"
            mock_config_instance.pdf_dpi = 150

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.DiagramGenerator'):
                mock_ocr = Mock()
                mock_ocr_cls.return_value = mock_ocr
                mock_ocr.extract_text = Mock(side_effect=Exception("OCR Error"))

                mock_extract_images.return_value = [Mock(), Mock()]

                processor = DocumentProcessor(config=mock_config_instance)

                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    temp_path = Path(f.name)

                try:
                    with pytest.raises(Exception, match="全ページのOCRに失敗しました"):
                        processor._extract_text_from_pdf(temp_path)
                finally:
                    temp_path.unlink(missing_ok=True)


class TestGenerateOutputsDiagramGeneration:
    """Test _generate_outputs with diagram generation (lines 323-360)"""

    @patch('src.processor.processor.create_formatted_pdf')
    @patch('src.processor.processor.create_word_document')
    @patch('src.processor.processor.create_audio_summary')
    @patch('src.processor.processor.DiagramGenerator')
    def test_generate_outputs_with_diagram_success(self, mock_diagram_cls, mock_audio, mock_docx, mock_pdf):
        """Test successful diagram generation"""
        mock_config = Mock()
        mock_config.generate_diagram = True
        mock_config.generate_diagram_png = True
        mock_config.generate_diagram_mermaid = True
        mock_config.output_directory = Path("./output")
        mock_config.gemini_model_name = "gemini-1.5-flash"
        mock_config.diagram_theme = "default"
        mock_config.diagram_width = 1920
        mock_config.diagram_height = 1080

        mock_diagram_result = Mock()
        mock_diagram_result.success = True
        mock_diagram_result.image_path = Path("./output/diagram.png")
        mock_diagram_result.mermaid_code = "graph TD"
        mock_diagram_result.markdown_path = Path("./output/diagram.md")
        mock_diagram_result.mermaid_path = Path("./output/diagram.mmd")
        mock_diagram_result.diagram_type = "flowchart"
        mock_diagram_result.error_message = None

        mock_diagram = Mock()
        mock_diagram.generate = Mock(return_value=mock_diagram_result)
        mock_diagram_cls.return_value = mock_diagram

        mock_pdf.return_value = "output.pdf"
        mock_docx.return_value = "output.docx"
        mock_audio.return_value = "output.mp3"

        with patch('src.processor.processor.Config.get_instance') as mock_config_get:
            mock_config_get.return_value = mock_config

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config)

                summary_result = Mock()
                summary_result.title = "Test"
                summary_result.summary = "Summary"
                summary_result.key_points = ["Point 1"]
                summary_result.sections = []
                summary_result.glossary = []

                result = processor._generate_outputs(
                    summary_result=summary_result,
                    pdf_path=Path("./test.pdf")
                )

                assert "diagram" in result
                assert "mermaid_code" in result
                assert result["mermaid_code"] == "graph TD"
                mock_diagram.generate.assert_called_once()

    @patch('src.processor.processor.create_formatted_pdf')
    @patch('src.processor.processor.create_word_document')
    @patch('src.processor.processor.create_audio_summary')
    @patch('src.processor.processor.DiagramGenerator')
    def test_generate_outputs_diagram_failure(self, mock_diagram_cls, mock_audio, mock_docx, mock_pdf):
        """Test diagram generation failure is handled gracefully"""
        mock_config = Mock()
        mock_config.generate_diagram = True
        mock_config.generate_diagram_png = False
        mock_config.generate_diagram_mermaid = False
        mock_config.output_directory = Path("./output")
        mock_config.gemini_model_name = "gemini-1.5-flash"
        mock_config.diagram_theme = "default"
        mock_config.diagram_width = 1920
        mock_config.diagram_height = 1080

        mock_diagram = Mock()
        mock_diagram.generate = Mock(side_effect=Exception("Diagram generation failed"))
        mock_diagram_cls.return_value = mock_diagram

        mock_pdf.return_value = "output.pdf"
        mock_docx.return_value = "output.docx"
        mock_audio.return_value = "output.mp3"

        with patch('src.processor.processor.Config.get_instance') as mock_config_get:
            mock_config_get.return_value = mock_config

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config)

                summary_result = Mock()
                summary_result.title = "Test"
                summary_result.summary = "Summary"
                summary_result.key_points = []
                summary_result.sections = []
                summary_result.glossary = []

                result = processor._generate_outputs(
                    summary_result=summary_result,
                    pdf_path=Path("./test.pdf")
                )

                assert result["diagram"] is None


class TestGenerateOutputsAudioFailure:
    """Test _generate_outputs with audio failure (lines 386-398)"""

    @patch('src.processor.processor.create_formatted_pdf')
    @patch('src.processor.processor.create_word_document')
    @patch('src.processor.processor.create_audio_summary')
    @patch('src.processor.processor.DiagramGenerator')
    def test_generate_outputs_audio_failure(self, mock_diagram_cls, mock_audio, mock_docx, mock_pdf):
        """Test audio generation failure is handled gracefully"""
        mock_config = Mock()
        mock_config.generate_diagram = False
        mock_config.output_directory = Path("./output")
        mock_config.gemini_model_name = "gemini-1.5-flash"

        mock_diagram = Mock()
        mock_diagram_cls.return_value = mock_diagram

        mock_pdf.return_value = "output.pdf"
        mock_docx.return_value = "output.docx"
        mock_audio.side_effect = Exception("Audio generation failed")

        with patch('src.processor.processor.Config.get_instance') as mock_config_get:
            mock_config_get.return_value = mock_config

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config)

                summary_result = Mock()
                summary_result.title = "Test"
                summary_result.summary = "Summary"
                summary_result.key_points = ["Point 1"]
                summary_result.sections = []
                summary_result.glossary = []

                result = processor._generate_outputs(
                    summary_result=summary_result,
                    pdf_path=Path("./test.pdf")
                )

                assert result["audio"] is None
                assert result["pdf"] is not None
                assert result["docx"] is not None


class TestGenerateOutputsPdfWordFailures:
    """Test _generate_outputs with PDF/Word failures (lines 370-372, 382-384)"""

    @patch('src.processor.processor.create_formatted_pdf')
    @patch('src.processor.processor.create_word_document')
    @patch('src.processor.processor.create_audio_summary')
    @patch('src.processor.processor.DiagramGenerator')
    def test_generate_outputs_pdf_failure(self, mock_diagram_cls, mock_audio, mock_docx, mock_pdf):
        """Test PDF generation failure is handled gracefully"""
        mock_config = Mock()
        mock_config.generate_diagram = False
        mock_config.output_directory = Path("./output")
        mock_config.gemini_model_name = "gemini-1.5-flash"

        mock_diagram = Mock()
        mock_diagram_cls.return_value = mock_diagram

        mock_pdf.side_effect = Exception("PDF generation failed")
        mock_docx.return_value = "output.docx"
        mock_audio.return_value = "output.mp3"

        with patch('src.processor.processor.Config.get_instance') as mock_config_get:
            mock_config_get.return_value = mock_config

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config)

                summary_result = Mock()
                summary_result.title = "Test"
                summary_result.summary = "Summary"
                summary_result.key_points = []
                summary_result.sections = []
                summary_result.glossary = []

                result = processor._generate_outputs(
                    summary_result=summary_result,
                    pdf_path=Path("./test.pdf")
                )

                assert result["pdf"] is None
                assert result["docx"] is not None

    @patch('src.processor.processor.create_formatted_pdf')
    @patch('src.processor.processor.create_word_document')
    @patch('src.processor.processor.create_audio_summary')
    @patch('src.processor.processor.DiagramGenerator')
    def test_generate_outputs_word_failure(self, mock_diagram_cls, mock_audio, mock_docx, mock_pdf):
        """Test Word generation failure is handled gracefully"""
        mock_config = Mock()
        mock_config.generate_diagram = False
        mock_config.output_directory = Path("./output")
        mock_config.gemini_model_name = "gemini-1.5-flash"

        mock_diagram = Mock()
        mock_diagram_cls.return_value = mock_diagram

        mock_pdf.return_value = "output.pdf"
        mock_docx.side_effect = Exception("Word generation failed")
        mock_audio.return_value = "output.mp3"

        with patch('src.processor.processor.Config.get_instance') as mock_config_get:
            mock_config_get.return_value = mock_config

            with patch('src.processor.processor.HandwrittenPromptBuilder.from_config'), \
                 patch('src.processor.processor.ProcessorFactory.create_processor'), \
                 patch('src.processor.processor.OCRProcessor'):
                processor = DocumentProcessor(config=mock_config)

                summary_result = Mock()
                summary_result.title = "Test"
                summary_result.summary = "Summary"
                summary_result.key_points = []
                summary_result.sections = []
                summary_result.glossary = []

                result = processor._generate_outputs(
                    summary_result=summary_result,
                    pdf_path=Path("./test.pdf")
                )

                assert result["pdf"] is not None
                assert result["docx"] is None

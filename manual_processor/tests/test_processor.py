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

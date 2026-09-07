"""
Tests for custom exceptions.
"""

import pytest

from src.exceptions import (
    ProcessingError,
    OCRError,
    PageOCRError,
    GeminiAPIError,
    TTSError,
    FileIOError,
    ConfigurationError,
    DiagramGenerationError,
    OutputGenerationError,
    PDFGenerationError,
    DocxGenerationError,
    TemplateNotFoundError,
    TemplateValidationError,
    EncryptionError,
    AuditLogError,
    USBDeviceError,
    I18nTranslationError,
    PromptEngineError,
)


class TestProcessingError:
    """Test base ProcessingError exception"""

    def test_create_with_message_only(self):
        """Test creating exception with just a message"""
        error = ProcessingError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.error_code == "PROCESSINGERROR"
        assert error.user_message == "Test error"
        assert error.recovery_hint is None

    def test_create_with_all_args(self):
        """Test creating exception with all arguments"""
        error = ProcessingError(
            message="Test error",
            error_code="E001",
            user_message="User-friendly message",
            recovery_hint="Try again"
        )
        assert error.message == "Test error"
        assert error.error_code == "E001"
        assert error.user_message == "User-friendly message"
        assert error.recovery_hint == "Try again"

    def test_error_code_default(self):
        """Test default error code is class name uppercased"""
        error = ProcessingError("test")
        assert error.error_code == "PROCESSINGERROR"

    def test_user_message_defaults_to_message(self):
        """Test user_message defaults to message"""
        error = ProcessingError("test message")
        assert error.user_message == "test message"

    def test_can_be_raised_and_caught(self):
        """Test exception can be raised and caught"""
        with pytest.raises(ProcessingError) as exc_info:
            raise ProcessingError("test")
        assert str(exc_info.value) == "test"


class TestSubclasses:
    """Test exception subclasses"""

    def test_ocr_error(self):
        """Test OCRError"""
        error = OCRError("OCR failed")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "OCRERROR"

    def test_page_ocr_error(self):
        """Test PageOCRError"""
        error = PageOCRError("Page OCR failed")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "PAGEOCRERROR"

    def test_gemini_api_error(self):
        """Test GeminiAPIError"""
        error = GeminiAPIError("Gemini API failed")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "GEMINIAPIERROR"

    def test_tts_error(self):
        """Test TTSError"""
        error = TTSError("TTS failed")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "TTSERROR"

    def test_file_io_error(self):
        """Test FileIOError"""
        error = FileIOError("File I/O failed")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "FILEIOERROR"

    def test_configuration_error(self):
        """Test ConfigurationError"""
        error = ConfigurationError("Config invalid")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "CONFIGURATIONERROR"

    def test_diagram_generation_error(self):
        """Test DiagramGenerationError"""
        error = DiagramGenerationError("Diagram failed")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "DIAGRAMGENERATIONERROR"

    def test_pdf_generation_error(self):
        """Test PDFGenerationError inherits from OutputGenerationError"""
        error = PDFGenerationError("PDF generation failed")
        assert isinstance(error, OutputGenerationError)
        assert isinstance(error, ProcessingError)

    def test_docx_generation_error(self):
        """Test DocxGenerationError inherits from OutputGenerationError"""
        error = DocxGenerationError("DOCX generation failed")
        assert isinstance(error, OutputGenerationError)
        assert isinstance(error, ProcessingError)

    def test_template_not_found_error(self):
        """Test TemplateNotFoundError"""
        error = TemplateNotFoundError("template.html")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "TEMPLATENOTFOUNDERROR"

    def test_template_validation_error(self):
        """Test TemplateValidationError"""
        error = TemplateValidationError("Invalid template")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "TEMPLATEVALIDATIONERROR"

    def test_encryption_error(self):
        """Test EncryptionError"""
        error = EncryptionError("Encryption failed")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "ENCRYPTIONERROR"

    def test_audit_log_error(self):
        """Test AuditLogError"""
        error = AuditLogError("Audit failed")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "AUDITLOGERROR"

    def test_usb_device_error(self):
        """Test USBDeviceError"""
        error = USBDeviceError("USB error")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "USBDEVICEERROR"

    def test_i18n_translation_error(self):
        """Test I18nTranslationError"""
        error = I18nTranslationError("Translation failed")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "I18NTRANSLATIONERROR"

    def test_prompt_engine_error(self):
        """Test PromptEngineError"""
        error = PromptEngineError("Prompt engine failed")
        assert isinstance(error, ProcessingError)
        assert error.error_code == "PROMPTENGINEERROR"


class TestExceptionHierarchy:
    """Test exception hierarchy and catching"""

    def test_catch_subclass_as_base(self):
        """Test that subclasses can be caught as base class"""
        with pytest.raises(ProcessingError):
            raise OCRError("test")

    def test_catch_pdf_as_output(self):
        """Test PDFGenerationError can be caught as OutputGenerationError"""
        with pytest.raises(OutputGenerationError):
            raise PDFGenerationError("test")

    def test_catch_docx_as_output(self):
        """Test DocxGenerationError can be caught as OutputGenerationError"""
        with pytest.raises(OutputGenerationError):
            raise DocxGenerationError("test")

    def test_exception_chaining(self):
        """Test exception chaining with 'from'"""
        try:
            try:
                raise ValueError("original")
            except ValueError as e:
                raise OCRError("wrapper") from e
        except OCRError as e:
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ValueError)

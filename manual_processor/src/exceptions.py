"""
Exception classes for the Manual Processor system
"""

class ProcessingError(Exception):
    """Base exception for all processing errors"""
    def __init__(self, message: str, error_code: str = None, user_message: str = None, recovery_hint: str = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.user_message = user_message or message
        self.recovery_hint = recovery_hint
        self.error_code = error_code or self.__class__.__name__.upper()


class OCRError(ProcessingError):
    """Exception raised for OCR processing errors"""
    pass


class PageOCRError(ProcessingError):
    """Exception raised for page-level OCR errors"""
    pass


class GeminiAPIError(ProcessingError):
    """Exception raised for Gemini API processing errors"""
    pass


class TTSError(ProcessingError):
    """Exception raised for Text-to-Speech processing errors"""
    pass


class FileIOError(ProcessingError):
    """Exception raised for file input/output errors"""
    pass


class ConfigurationError(ProcessingError):
    """Exception raised for configuration errors"""
    pass


class DiagramGenerationError(ProcessingError):
    """Exception raised for diagram generation errors"""
    pass


class OutputGenerationError(ProcessingError):
    """Exception raised for output generation errors"""
    pass


class PDFGenerationError(OutputGenerationError):
    """Exception raised for PDF generation errors"""
    pass


class DocxGenerationError(OutputGenerationError):
    """Exception raised for Word document generation errors"""
    pass
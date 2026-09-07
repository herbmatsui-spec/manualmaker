"""
Test helper utilities for Manual Processor tests.
Provides common test functions to reduce boilerplate.
"""

import os
import io
import tempfile
from pathlib import Path
from typing import Optional, Generator

import pytest

from tests.fixtures.sample_pdfs import create_sample_pdf, create_handwritten_sample_pdf


def create_temp_dir() -> Path:
    """
    Create a temporary directory for tests.
    
    Returns:
        Path to temporary directory
    """
    return Path(tempfile.mkdtemp())


def cleanup_temp_dir(path: Path) -> None:
    """
    Clean up temporary directory.
    
    Args:
        path: Path to directory to remove
    """
    if path.exists():
        import shutil
        shutil.rmtree(path, ignore_errors=True)


def assert_valid_pdf(data: bytes) -> None:
    """
    Assert that bytes contain valid PDF data.
    
    Args:
        data: PDF file content as bytes
    """
    assert data, "PDF data is empty"
    assert data.startswith(b"%PDF-"), f"Invalid PDF magic bytes: {data[:10]}"
    assert b"%%EOF" in data, "PDF missing EOF marker"


def mock_gemini_response(text: str = "This is a mocked Gemini response") -> dict:
    """
    Create a mock Gemini API response.
    
    Args:
        text: Response text
        
    Returns:
        Mock response dictionary
    """
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": text}
                    ],
                    "role": "model"
                },
                "finishReason": "STOP",
                "index": 0
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 100,
            "candidatesTokenCount": 50,
            "totalTokenCount": 150
        }
    }


def mock_vision_response(text: str = "Mocked OCR text") -> dict:
    """
    Create a mock Google Cloud Vision API response.
    
    Args:
        text: OCR text
        
    Returns:
        Mock response dictionary
    """
    return {
        "responses": [
            {
                "textAnnotations": [
                    {
                        "description": text,
                        "boundingPoly": {
                            "vertices": [
                                {"x": 0, "y": 0},
                                {"x": 100, "y": 0},
                                {"x": 100, "y": 100},
                                {"x": 0, "y": 100}
                            ]
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Pytest fixture for temporary directory.
    
    Yields:
        Path to temporary directory
    """
    path = create_temp_dir()
    yield path
    cleanup_temp_dir(path)


@pytest.fixture
def sample_pdf() -> bytes:
    """
    Pytest fixture for sample PDF.
    
    Returns:
        Sample PDF content as bytes
    """
    return create_sample_pdf(num_pages=1)


@pytest.fixture
def sample_pdf_multipage() -> bytes:
    """
    Pytest fixture for multi-page sample PDF.
    
    Returns:
        Multi-page PDF content as bytes
    """
    return create_sample_pdf(num_pages=5)


@pytest.fixture
def handwritten_pdf() -> bytes:
    """
    Pytest fixture for handwritten sample PDF.
    
    Returns:
        Handwritten PDF content as bytes
    """
    return create_handwritten_sample_pdf()


def set_env_vars(**kwargs) -> dict:
    """
    Set environment variables for testing and return original values.
    
    Args:
        **kwargs: Environment variables to set
        
    Returns:
        Dictionary of original values for cleanup
    """
    originals = {}
    for key, value in kwargs.items():
        originals[key] = os.environ.get(key)
        os.environ[key] = str(value)
    return originals


def restore_env_vars(originals: dict) -> None:
    """
    Restore environment variables to original values.
    
    Args:
        originals: Dictionary of original values from set_env_vars
    """
    for key, original in originals.items():
        if original is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original


class MockUploadFile:
    """Mock UploadFile for testing"""

    def __init__(self, filename: str, content: bytes, content_type: str = "application/pdf"):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._position = 0

    async def read(self, size: int = -1) -> bytes:
        if size == -1:
            result = self._content[self._position:]
            self._position = len(self._content)
            return result
        result = self._content[self._position:self._position + size]
        self._position += len(result)
        return result

    def seek(self, position: int) -> None:
        self._position = position

    def tell(self) -> int:
        return self._position

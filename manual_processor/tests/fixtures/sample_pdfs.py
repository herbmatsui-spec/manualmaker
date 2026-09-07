"""
Test fixtures for integration and E2E tests.
Provides sample PDF files and test data generators.
"""

import io
from pathlib import Path
from typing import Optional


def create_sample_pdf(num_pages: int = 1, content: Optional[str] = None) -> bytes:
    """
    Create a minimal valid PDF file for testing.
    
    Args:
        num_pages: Number of pages to create
        content: Optional text content to include
        
    Returns:
        PDF file content as bytes
    """
    # Minimal valid PDF structure
    pdf_parts = [
        b"%PDF-1.4\n",
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [",
    ]
    
    # Add pages
    for i in range(num_pages):
        page_obj_num = 3 + i
        pdf_parts.append(f" {page_obj_num} 0 R".encode())
    
    pdf_parts.extend([
        b"] /Count ", str(num_pages).encode(), b" >>\nendobj\n"
    ])
    
    # Add page objects
    for i in range(num_pages):
        page_obj_num = 3 + i
        pdf_parts.extend([
            f"{page_obj_num} 0 obj\n".encode(),
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\n",
            b"endobj\n"
        ])
    
    # Add trailer
    xref_offset = sum(len(part) for part in pdf_parts)
    pdf_parts.extend([
        b"xref\n",
        f"0 {3 + num_pages}\n".encode(),
        b"0000000000 65535 f \n",
    ])
    
    # Add xref entries
    for i in range(3 + num_pages):
        pdf_parts.append(f"{i * 100:010d} 00000 n \n".encode())
    
    pdf_parts.extend([
        b"trailer\n",
        f"<< /Size {3 + num_pages} /Root 1 0 R >>\n".encode(),
        b"startxref\n",
        str(xref_offset).encode(), b"\n",
        b"%%EOF\n"
    ])
    
    return b"".join(pdf_parts)


def create_handwritten_sample_pdf() -> bytes:
    """
    Create a sample PDF that simulates handwritten content.
    
    Returns:
        PDF file content as bytes
    """
    return create_sample_pdf(num_pages=2, content="手書きマニュアルサンプル")


def create_invalid_pdf() -> bytes:
    """
    Create invalid PDF content for testing validation.
    
    Returns:
        Invalid file content as bytes
    """
    return b"This is not a PDF file"


def create_large_pdf(target_size_mb: float = 1.0) -> bytes:
    """
    Create a PDF of approximately target size for testing size limits.
    
    Args:
        target_size_mb: Target size in megabytes
        
    Returns:
        Large PDF content as bytes
    """
    base_pdf = create_sample_pdf(num_pages=10)
    # Pad to target size
    current_size = len(base_pdf)
    target_size = int(target_size_mb * 1024 * 1024)
    
    if current_size >= target_size:
        return base_pdf
    
    # Add padding
    padding_size = target_size - current_size
    padding = b"%" + (b"x" * (padding_size - 1))
    
    return base_pdf + padding

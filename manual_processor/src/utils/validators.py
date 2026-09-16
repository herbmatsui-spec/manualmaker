"""
Input validation utilities for Manual Processor.
Provides common validation functions for API requests and file uploads.
"""

import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# PDF magic bytes
PDF_MAGIC_BYTES = b"%PDF-"

# Allowed languages
ALLOWED_LANGUAGES = frozenset(["ja", "en", "zh", "ko", "es"])

# UUID v4 pattern (32 hex chars without hyphens, or with hyphens)
UUID_PATTERN = re.compile(
    r"^[a-f0-9]{8}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{12}$",
    re.IGNORECASE,
)

# Safe filename pattern
SAFE_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def validate_file_size(size_mb: float, max_mb: float) -> bool:
    """
    Validate file size in megabytes.

    Args:
        size_mb: File size in MB
        max_mb: Maximum allowed size in MB

    Returns:
        True if size is within limit, False otherwise
    """
    if size_mb < 0:
        logger.warning(f"Invalid file size: {size_mb}MB (negative)")
        return False
    if size_mb > max_mb:
        logger.warning(
            f"File too large: {size_mb:.1f}MB > {max_mb:.1f}MB"
        )
        return False
    return True


def validate_pdf_content(data: bytes) -> bool:
    """
    Validate PDF file content by checking magic bytes.

    Args:
        data: File content as bytes

    Returns:
        True if content starts with PDF magic bytes, False otherwise
    """
    if not data or len(data) < len(PDF_MAGIC_BYTES):
        return False
    return data.startswith(PDF_MAGIC_BYTES)


def validate_uuid(s: str) -> bool:
    """
    Validate UUID v4 format (with or without hyphens).

    Args:
        s: String to validate

    Returns:
        True if valid UUID format, False otherwise
    """
    if not s or not isinstance(s, str):
        return False
    return bool(UUID_PATTERN.match(s))


def validate_language_code(lang: str) -> bool:
    """
    Validate language code against allowed list.

    Args:
        lang: Language code to validate

    Returns:
        True if language is in allowed list, False otherwise
    """
    if not lang or not isinstance(lang, str):
        return False
    return lang.lower() in ALLOWED_LANGUAGES


def validate_filename(filename: str) -> bool:
    """
    Validate filename for safety (no path traversal, only safe chars).

    Args:
        filename: Filename to validate

    Returns:
        True if filename is safe, False otherwise
    """
    if not filename or not isinstance(filename, str):
        return False
    if len(filename) > 255:
        return False
    # Check for path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    return bool(SAFE_FILENAME_PATTERN.match(filename))


def validate_extension(filename: str, allowed_extensions: list) -> bool:
    """
    Validate file extension against allowed list.

    Args:
        filename: Filename to check
        allowed_extensions: List of allowed extensions (e.g., ['.pdf'])

    Returns:
        True if extension is allowed, False otherwise
    """
    if not filename:
        return False
    ext = Path(filename).suffix.lower()
    allowed = [e.lower() if e.startswith(".") else f".{e.lower()}" for e in allowed_extensions]
    return ext in allowed


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and unsafe characters.
    
    Args:
        filename: Original filename (may contain path components)
        
    Returns:
        Sanitized filename safe for filesystem use
    """
    if not filename or not isinstance(filename, str):
        return "upload"
    
    # Get basename to prevent path traversal
    basename = Path(filename).name
    
    # If basename is empty after extracting, use default
    if not basename:
        basename = "upload"
    
    # Replace dangerous characters with underscore
    # Keep alphanumeric, Japanese/Korean/Chinese characters, dots, hyphens, underscores, spaces
    # Remove control characters, path separators, and other dangerous chars
    import re
    # Replace control characters (0x00-0x1f, 0x7f), path separators, and null bytes
    sanitized = re.sub(r'[\x00-\x1f\x7f\\/:*?"<>|]', '_', basename)
    
    # Remove leading/trailing dots and spaces (but keep internal ones)
    sanitized = sanitized.strip('. ')
    
    # Ensure not empty after stripping
    if not sanitized:
        sanitized = "upload"
    
    # Limit length to 255 bytes (typical filesystem limit)
    # Handle multi-byte characters by checking byte length
    if len(sanitized.encode('utf-8')) > 255:
        # Truncate by characters until under 255 bytes
        for i in range(len(sanitized), 0, -1):
            if len(sanitized[:i].encode('utf-8')) <= 255:
                sanitized = sanitized[:i]
                break
        # If still too long (shouldn't happen), force truncate
        if len(sanitized.encode('utf-8')) > 255:
            sanitized = sanitized[:255]
    
    # Ensure extension is preserved if possible
    # Extract extension from original basename if it's safe
    original_ext = Path(basename).suffix.lower()
    # Only keep extension if it's alphanumeric + dot and reasonable length
    if original_ext and len(original_ext) <= 10 and all(c.isalnum() or c == '.' for c in original_ext):
        # If our sanitized version doesn't end with this extension, add it
        if not sanitized.lower().endswith(original_ext):
            # Remove any existing extension from sanitized
            stem = Path(sanitized).stem
            sanitized = stem + original_ext
    # If no safe extension, default to .pdf for uploads (but caller should enforce)
    
    return sanitized

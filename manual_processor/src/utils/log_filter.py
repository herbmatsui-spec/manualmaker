"""
Log filtering utilities to prevent sensitive data leakage.
Automatically masks sensitive information in log messages.
"""

import re
import logging
from typing import Optional, List, Pattern

logger = logging.getLogger(__name__)


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter that masks sensitive data in log records.
    
    Masks:
    - API keys (api_key=..., key=...)
    - Email addresses
    - Bearer tokens
    - Credit card numbers
    - Phone numbers
    """

    # Patterns to mask
    PATTERNS: List[tuple[Pattern, str]] = [
        # API keys
        (re.compile(r'(api[_-]?key\s*[=:]\s*)\S+', re.IGNORECASE), r'\1[REDACTED]'),
        (re.compile(r'(key\s*[=:]\s*)\S{8,}', re.IGNORECASE), r'\1[REDACTED]'),
        
        # Bearer tokens
        (re.compile(r'(Bearer\s+)\S+', re.IGNORECASE), r'\1[REDACTED]'),
        
        # Email addresses
        (re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'), '[REDACTED_EMAIL]'),
        
        # Credit card numbers
        (re.compile(r'\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[ -]?\d{4}[ -]?\d{4}[ -]?\d{1,4}\b'), '[REDACTED_CARD]'),
        
        # Phone numbers (Japanese)
        (re.compile(r'0\d{1,4}-\d{1,4}-\d{4}'), '[REDACTED_PHONE]'),
        
        # My Number
        (re.compile(r'\b\d{4}-\d{4}-\d{4}\b'), '[REDACTED_MYNUMBER]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log record and mask sensitive data.
        
        Args:
            record: Log record to filter
            
        Returns:
            True to allow the record
        """
        if isinstance(record.msg, str):
            record.msg = self._mask_sensitive(record.msg)
        
        if record.args:
            record.args = tuple(
                self._mask_sensitive(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        return True

    def _mask_sensitive(self, text: str) -> str:
        """Apply all masking patterns to text"""
        masked = text
        for pattern, replacement in self.PATTERNS:
            masked = pattern.sub(replacement, masked)
        return masked


def apply_sensitive_data_filter(logger_name: Optional[str] = None) -> None:
    """
    Apply sensitive data filter to logger.
    
    Args:
        logger_name: Logger name to apply filter to, or None for root logger
    """
    target_logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    filter_instance = SensitiveDataFilter()
    
    # Avoid duplicate filters
    for f in target_logger.filters:
        if isinstance(f, SensitiveDataFilter):
            return
    
    target_logger.addFilter(filter_instance)
    logger.debug(f"Applied sensitive data filter to logger: {logger_name or 'root'}")


def mask_sensitive(text: str) -> str:
    """
    Mask sensitive data in text string.
    
    Args:
        text: Input text to mask
        
    Returns:
        Text with sensitive data masked
    """
    filter_instance = SensitiveDataFilter()
    return filter_instance._mask_sensitive(text)

"""
Noise Handler Module
Handles exclusion of noise elements like grid lines, stains, eraser marks
"""

import re
import logging
from typing import List, Set

logger = logging.getLogger(__name__)

NOISE_PATTERNS: List[str] = [
    r'^[─━‐]+$',
    r'^[│┃|]+$',
    r'^[・:;.।]{1,3}$',
    r'^[\s\t]+$',
]

RULE_LINE_CHARS: Set[str] = set('─━‐―│┃|')


class NoiseHandler:
    """Handler for detecting and excluding noise from OCR output"""

    def __init__(self):
        self.enabled = True
        self._noise_count = 0

    def is_noise_line(self, text: str) -> bool:
        """
        Determine if text is likely a noise element (line, dot pattern)

        Args:
            text: The text to check

        Returns:
            True if text appears to be noise, False otherwise
        """
        if not text:
            return False

        text_stripped = text.strip()

        if not text_stripped:
            return False

        if len(text_stripped) <= 3:
            for pattern in NOISE_PATTERNS:
                if re.match(pattern, text_stripped):
                    return True

        non_space_chars = [c for c in text_stripped if not c.isspace()]
        char_count = sum(1 for c in non_space_chars if c in RULE_LINE_CHARS)
        if non_space_chars and char_count == len(non_space_chars) and len(non_space_chars) >= 1:
            return True

        return False

    def is_noise_word(self, word: str) -> bool:
        """
        Determine if a single word/token is noise

        Args:
            word: The word to check

        Returns:
            True if word appears to be noise, False otherwise
        """
        if not word:
            return False

        word_stripped = word.strip()

        if not word_stripped:
            return True

        if re.match(r'^[─━‐―│┃|.\-:;*_=~^°'+"]+$", word_stripped):
            return True

        if len(word_stripped) <= 2 and re.match(r'^[・.。,，;；:：]+$', word_stripped):
            return True

        return False

    def remove_noise_from_text(self, text: str) -> str:
        """
        Remove noise elements from OCR output

        Args:
            text: OCR output text

        Returns:
            Cleaned text with noise removed
        """
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            if self.is_noise_line(line):
                self._noise_count += 1
                continue

            words = line.split()
            cleaned_words = []

            for word in words:
                if not self.is_noise_word(word):
                    cleaned_words.append(word)

            cleaned_line = ' '.join(cleaned_words)
            if cleaned_line.strip():
                cleaned_lines.append(cleaned_line)

        return '\n'.join(cleaned_lines)

    def get_noise_count(self) -> int:
        """Return the number of noise elements removed"""
        return self._noise_count

    def reset_noise_count(self) -> None:
        """Reset the noise counter"""
        self._noise_count = 0

    def validate_clean(self, text: str) -> List[str]:
        """
        Validate that text does not contain noise elements

        Args:
            text: Text to validate

        Returns:
            List of issues found
        """
        issues = []
        lines = text.split('\n')

        for line_num, line in enumerate(lines, 1):
            if self.is_noise_line(line):
                issues.append(f"Line {line_num}: '{line[:20]}...' appears to be noise (line/rule)")

            words = line.split()
            for word in words:
                if self.is_noise_word(word):
                    issues.append(f"Line {line_num}: '{word}' appears to be noise symbol")

        return issues

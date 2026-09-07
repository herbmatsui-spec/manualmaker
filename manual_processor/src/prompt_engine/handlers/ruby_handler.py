"""
Ruby Handler Module
Handles ruby text (furigana) exclusion from transcription
"""

import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

RUBY_PATTERNS: List[Tuple[str, str]] = [
    (r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]([\u3040-\u309F\u30A0-\u30FF]+)', r'\1'),
]

RUBY_SIZE_THRESHOLD: float = 0.5


class RubyHandler:
    """Handler for detecting and excluding ruby text from OCR output"""

    def __init__(self):
        self.enabled = True

    def is_ruby_text(self, text: str, position: Tuple[int, int] = None) -> bool:
        """
        Determine if text appears to be ruby (furigana)

        Args:
            text: The text to check
            position: Optional (x, y) position tuple for additional context

        Returns:
            True if text appears to be ruby, False otherwise
        """
        if not text:
            return False

        if len(text) > 3:
            return False

        if re.match(r'^[\u3040-\u309F\u30A0-\u30FF]+$', text):
            return True

        return False

    def extract_ruby_from_text(self, text: str) -> Tuple[str, List[str]]:
        """
        Extract ruby text and return clean main text

        Args:
            text: Mixed text that may contain ruby

        Returns:
            Tuple of (clean_text, list_of_extracted_ruby)
        """
        extracted_ruby = []

        ruby_pattern = r'([\u3040-\u309F\u30A0-\u30FF]{1,4})'
        matches = list(re.finditer(ruby_pattern, text))

        if not matches:
            return text, []

        cleaned_parts = []
        last_end = 0

        for match in matches:
            ruby_char = match.group(1)
            start = match.start()

            before_char = text[start - 1] if start > 0 else ''
            after_char = text[match.end()] if match.end() < len(text) else ''

            before_is_kanji = re.match(r'[\u4E00-\u9FFF]', before_char) if before_char else False
            after_is_kanji = re.match(r'[\u4E00-\u9FFF]', after_char) if after_char else False

            if start > last_end:
                cleaned_parts.append(text[last_end:start])

            if before_is_kanji and after_is_kanji:
                extracted_ruby.append(ruby_char)
            else:
                cleaned_parts.append(ruby_char)

            last_end = match.end()

        if last_end < len(text):
            cleaned_parts.append(text[last_end:])

        return ''.join(cleaned_parts), extracted_ruby

    def post_process_text(self, text: str) -> str:
        """
        Post-process OCR text to remove ruby artifacts

        Args:
            text: OCR output text

        Returns:
            Cleaned text with ruby removed
        """
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            cleaned_line, _ = self.extract_ruby_from_text(line)
            cleaned_lines.append(cleaned_line)

        return '\n'.join(cleaned_lines)

    def validate_no_ruby(self, text: str) -> List[str]:
        """
        Validate that text does not contain embedded ruby characters

        Args:
            text: Text to validate

        Returns:
            List of positions where ruby-like characters were found embedded in kanji context
        """
        issues = []
        lines = text.split('\n')

        for line_num, line in enumerate(lines, 1):
            ruby_pattern = r'([\u3040-\u309F\u30A0-\u30FF]{1,4})'
            matches = re.finditer(ruby_pattern, line)

            for match in matches:
                char = match.group()
                start_pos = match.start()
                end_pos = match.end()

                before_kanji = False
                after_kanji = False

                if start_pos > 0:
                    before_char = line[start_pos - 1]
                    before_kanji = bool(re.match(r'[\u4E00-\u9FFF]', before_char))

                if end_pos < len(line):
                    after_char = line[end_pos]
                    after_kanji = bool(re.match(r'[\u4E00-\u9FFF]', after_char))

                if before_kanji and after_kanji:
                    issues.append(f"Line {line_num}: '{char}' between kanji at position {start_pos} may be furigana (ruby)")

        return issues

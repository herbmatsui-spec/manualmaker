"""
Validators Module
Validates prompt output and OCR results for compliance with transcription rules
"""

import re
import logging
from typing import List, Tuple

from src.prompt_engine.handlers.ruby_handler import RubyHandler
from src.prompt_engine.handlers.noise_handler import NoiseHandler
from src.prompt_engine.handlers.quality_handler import QualityHandler

logger = logging.getLogger(__name__)


class PromptOutputValidator:
    """Validates that OCR/transcription output complies with prompt rules"""

    def __init__(self):
        self.ruby_handler = RubyHandler()
        self.noise_handler = NoiseHandler()
        self.quality_handler = QualityHandler()
        self.issues: List[str] = []

    def validate_no_summarization(self, original_text: str, output_text: str) -> bool:
        """
        Check that output is not a summarization

        Args:
            original_text: Original OCR text
            output_text: AI response text

        Returns:
            True if not summarized, False if summarization detected
        """
        if not output_text or not output_text.strip():
            return True

        output_len = len(output_text.strip())
        original_len = len(original_text.strip()) if original_text else 0

        if original_len > 0 and output_len < original_len * 0.5:
            self.issues.append("出力が元のテキストより大幅に短いです。要約された可能性があります。")
            return False

        summary_indicators = [
            "要約", "まとめ", "概要", "summary",
            " всего ", "略して", "つまり",
        ]
        for indicator in summary_indicators:
            if indicator in output_text[:100]:
                self.issues.append(f"要約を示す表現が検出されました: '{indicator}'")
                return False

        return True

    def validate_unreadable_markers(self, text: str, marker: str = "●") -> bool:
        """
        Check that unreadable markers are used correctly

        Args:
            text: Output text
            marker: Expected marker string

        Returns:
            True if markers used correctly
        """
        if not text:
            return True

        if marker not in text:
            return True

        lines = text.split('\n')
        marker_lines = [l for l in lines if marker in l]

        for line in marker_lines:
            line_cleaned = line.replace(marker, "").strip()
            if len(line_cleaned) > 5:
                self.issues.append(f"マーカー' {marker}'が密集したテキストと共に使用されています。")
                return False

        return True

    def validate_no_ruby_artifacts(self, text: str) -> bool:
        """
        Check that ruby text is not embedded in output

        Args:
            text: Output text

        Returns:
            True if no ruby artifacts
        """
        issues = self.ruby_handler.validate_no_ruby(text)
        if issues:
            self.issues.extend(issues)
            return False
        return True

    def validate_no_noise(self, text: str) -> bool:
        """
        Check that noise elements are removed

        Args:
            text: Output text

        Returns:
            True if no noise detected
        """
        noise_issues = self.noise_handler.validate_clean(text)
        if noise_issues:
            self.issues.extend(noise_issues)
            return False
        return True

    def validate_content_quality(self, text: str) -> bool:
        """
        Check overall content quality

        Args:
            text: Output text

        Returns:
            True if quality is acceptable
        """
        quality_issues = self.quality_handler.detect_low_quality_indicators(text)
        if quality_issues:
            for issue in quality_issues:
                if issue != "excessive_special_chars":
                    self.issues.append(f"品質問題: {issue}")
            return len([i for i in quality_issues if i != "excessive_special_chars"]) == 0
        return True

    def validate_complete(self, text: str) -> Tuple[bool, List[str]]:
        """
        Run all validation checks

        Args:
            text: Output text to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        self.issues.clear()

        is_complete, completeness_issues = self.quality_handler.validate_content_completeness(text)
        if not is_complete:
            self.issues.extend(completeness_issues)

        if not text or not text.strip():
            self.issues.append("出力が空です")
            return False, self.issues

        self.validate_no_noise(text)
        self.validate_no_ruby_artifacts(text)

        return len(self.issues) == 0, self.issues

    def get_issues(self) -> List[str]:
        """Return list of validation issues"""
        return list(self.issues)

    def reset(self) -> None:
        """Reset validator state"""
        self.issues.clear()

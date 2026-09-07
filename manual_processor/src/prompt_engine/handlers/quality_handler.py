"""
Quality Handler Module
Handles low quality image detection and processing
"""

import re
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class QualityHandler:
    """Handler for detecting and processing low quality OCR output"""

    def __init__(self):
        self.enabled = True
        self.low_quality_threshold = 0.5

    def detect_low_quality_indicators(self, text: str) -> List[str]:
        """
        Detect indicators of low quality OCR

        Args:
            text: OCR output text

        Returns:
            List of detected quality issues
        """
        issues = []

        if not text:
            issues.append("empty_text")
            return issues

        lines = text.split('\n')
        if len(lines) < 3 and len(text) > 100:
            issues.append("insufficient_lines")

        special_chars = sum(1 for c in text if c in '�□�！？')
        if special_chars > len(text) * 0.05:
            issues.append("excessive_special_chars")

        if re.search(r'[I|l|][I|l|][I|l|]', text):
            issues.append("repeated_ambiguous_chars")

        low_confidence_patterns = [
            r'[\u4e00-\u9fff]{1,2}[\?\。\．]',
        ]
        for pattern in low_confidence_patterns:
            if re.search(pattern, text):
                issues.append("low_confidence_markers")

        if len(text) > 0:
            avg_line_len = len(text) / len(lines) if lines else 0
            if avg_line_len < 3 and len(lines) > 10:
                issues.append("unusually_short_lines")

        return issues

    def has_adequate_content(self, text: str, min_chars: int = 50) -> bool:
        """
        Check if text has adequate content

        Args:
            text: OCR output text
            min_chars: Minimum expected character count

        Returns:
            True if content is adequate
        """
        if not text or not text.strip():
            return False

        actual_chars = len(text.strip())
        return actual_chars >= min_chars

    def detect_fragmented_text(self, text: str) -> List[str]:
        """
        Detect fragmented or incomplete text patterns

        Args:
            text: OCR output text

        Returns:
            List of detected fragmentation issues
        """
        fragments = []

        lines = text.split('\n')
        for i, line in enumerate(lines):
            if len(line.strip()) == 1 and i > 0 and i < len(lines) - 1:
                prev_len = len(lines[i-1].strip()) if i > 0 else 0
                next_len = len(lines[i+1].strip()) if i < len(lines) - 1 else 0
                if prev_len > 5 and next_len > 5:
                    fragments.append(f"Line {i+1}: Single character line between longer lines")

            if re.match(r'^[a-zA-Z0-9]{1,3}$', line.strip()) and len(line.strip()) > 0:
                if i > 0 and i < len(lines) - 1:
                    prev_has_jp = bool(re.search(r'[\u4e00-\u9fff]', lines[i-1]))
                    next_has_jp = bool(re.search(r'[\u4e00-\u9fff]', lines[i+1]))
                    if prev_has_jp and next_has_jp:
                        fragments.append(f"Line {i+1}: Isolated alphanumeric '{line.strip()}' between Japanese text")

        return fragments

    def suggest_quality_improvements(self, text: str) -> List[str]:
        """
        Suggest improvements for low quality text

        Args:
            text: OCR output text

        Returns:
            List of improvement suggestions
        """
        suggestions = []
        issues = self.detect_low_quality_indicators(text)

        if "empty_text" in issues:
            suggestions.append("OCRがテキストを抽出できませんでした。画像解像度を確認してください。")

        if "excessive_special_chars" in issues:
            suggestions.append("特殊文字过多です。再スキャンまたは画像品質の改善を検討してください。")

        if "repeated_ambiguous_chars" in issues:
            suggestions.append("！「」糊された可能性のある文字が検出されました。")

        if "low_confidence_markers" in issues:
            suggestions.append("低信頼度マーカーが検出されました。")

        if not suggestions:
            suggestions.append("テキスト品質は良好です。")

        return suggestions

    def validate_content_completeness(self, text: str) -> Tuple[bool, List[str]]:
        """
        Validate that OCR content is complete

        Args:
            text: OCR output text

        Returns:
            Tuple of (is_complete, list_of_issues)
        """
        issues = []

        if not text or not text.strip():
            return False, ["テキストが空です"]

        lines = text.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]

        if len(non_empty_lines) == 0:
            issues.append("改行を含むテキストがありません")

        total_chars = sum(len(l) for l in non_empty_lines)
        if total_chars < 20:
            issues.append(f"テキストが短すぎます（{total_chars}文字）")

        bracket_pairs = [('（', '）'), ('[', ']'), ('【', '】')]
        for open_b, close_b in bracket_pairs:
            open_count = text.count(open_b)
            close_count = text.count(close_b)
            if open_count != close_count and open_count > 0:
                issues.append(f"括弧が閉じられていません: {open_b}={open_count}, {close_b}={close_count}")

        return len(issues) == 0, issues

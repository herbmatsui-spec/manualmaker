"""
Tests for Quality Handler Module
"""

import pytest
from src.prompt_engine.handlers.quality_handler import QualityHandler


class TestQualityHandler:
    """Tests for QualityHandler class"""

    def test_initialization(self):
        handler = QualityHandler()
        assert handler.enabled == True
        assert handler.low_quality_threshold == 0.5

    def test_detect_low_quality_indicators_empty(self):
        handler = QualityHandler()
        issues = handler.detect_low_quality_indicators("")
        assert "empty_text" in issues

    def test_detect_low_quality_indicators_normal(self):
        handler = QualityHandler()
        text = "これは正常なテキストです。売上総利益の計算方法について説明します。"
        issues = handler.detect_low_quality_indicators(text)
        assert "empty_text" not in issues

    def test_detect_low_quality_indicators_special_chars(self):
        handler = QualityHandler()
        text = "これは文本です？？？"
        issues = handler.detect_low_quality_indicators(text)
        assert isinstance(issues, list)

    def test_has_adequate_content_true(self):
        handler = QualityHandler()
        text = "これは十分な長さを持つテキストです。何か意味のある内容が含まれています。"
        assert handler.has_adequate_content(text, min_chars=30) == True

    def test_has_adequate_content_false(self):
        handler = QualityHandler()
        text = "短い"
        assert handler.has_adequate_content(text, min_chars=50) == False

    def test_has_adequate_content_empty(self):
        handler = QualityHandler()
        assert handler.has_adequate_content("") == False
        assert handler.has_adequate_content("   ") == False

    def test_detect_fragmented_text(self):
        handler = QualityHandler()
        text = "長いテキスト\nX\n長いテキスト"
        fragments = handler.detect_fragmented_text(text)
        assert isinstance(fragments, list)

    def test_detect_fragmented_text_normal(self):
        handler = QualityHandler()
        text = "これは正常な\n複数行の\nテキストです"
        fragments = handler.detect_fragmented_text(text)
        assert len(fragments) == 0

    def test_suggest_quality_improvements(self):
        handler = QualityHandler()
        text = ""
        suggestions = handler.suggest_quality_improvements(text)
        assert len(suggestions) > 0
        assert "empty" in suggestions[0].lower() or "抽出" in suggestions[0]

    def test_suggest_quality_improvements_normal(self):
        handler = QualityHandler()
        text = "これは正常な日本語のテキストです"
        suggestions = handler.suggest_quality_improvements(text)
        assert len(suggestions) > 0
        assert "良好" in suggestions[0]

    def test_validate_content_completeness_valid(self):
        handler = QualityHandler()
        text = "これは正常な日本語のテキストです。十分な長さと内容があります。"
        is_complete, issues = handler.validate_content_completeness(text)
        assert is_complete == True
        assert len(issues) == 0

    def test_validate_content_completeness_empty(self):
        handler = QualityHandler()
        is_complete, issues = handler.validate_content_completeness("")
        assert is_complete == False
        assert len(issues) > 0

    def test_validate_content_completeness_short(self):
        handler = QualityHandler()
        text = "短い"
        is_complete, issues = handler.validate_content_completeness(text)
        assert is_complete == False

    def test_validate_content_completeness_unmatched_brackets(self):
        handler = QualityHandler()
        text = "これは（テストです"
        is_complete, issues = handler.validate_content_completeness(text)
        assert is_complete == False
        assert len(issues) > 0

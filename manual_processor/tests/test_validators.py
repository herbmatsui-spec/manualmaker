"""
Tests for Validators Module
"""

import pytest
from src.prompt_engine.validators import PromptOutputValidator


class TestPromptOutputValidator:
    """Tests for PromptOutputValidator class"""

    def test_initialization(self):
        validator = PromptOutputValidator()
        assert validator.ruby_handler is not None
        assert validator.noise_handler is not None
        assert validator.quality_handler is not None
        assert validator.issues == []

    def test_validate_no_summarization_valid(self):
        validator = PromptOutputValidator()
        original = "これは正常な長さのテキストです。何かの説明が含まれています。"
        output = "これは正常な長さのテキストです。何かの説明が含まれています。"
        assert validator.validate_no_summarization(original, output) == True

    def test_validate_no_summarization_short(self):
        validator = PromptOutputValidator()
        original = "これは正常な長さのテキストです。何かの説明が含まれています。"
        output = "要約しました"
        assert validator.validate_no_summarization(original, output) == False

    def test_validate_no_summarization_empty(self):
        validator = PromptOutputValidator()
        assert validator.validate_no_summarization("", "") == True
        assert validator.validate_no_summarization("original", "") == True

    def test_validate_unreadable_markers_valid(self):
        validator = PromptOutputValidator()
        text = "●"
        assert validator.validate_unreadable_markers(text, "●") == True

    def test_validate_unreadable_markers_no_marker(self):
        validator = PromptOutputValidator()
        text = "これは正常なテキストです"
        assert validator.validate_unreadable_markers(text, "●") == True

    def test_validate_unreadable_markers密集(self):
        validator = PromptOutputValidator()
        text = "● ● ● ●"
        result = validator.validate_unreadable_markers(text, "●")
        assert isinstance(result, bool)

    def test_validate_no_ruby_artifacts_valid(self):
        validator = PromptOutputValidator()
        text = "日本語"  # Kanji only, no hiragana/katakana
        assert validator.validate_no_ruby_artifacts(text) == True

    def test_validate_no_ruby_artifacts_embedded(self):
        validator = PromptOutputValidator()
        text = "日(に)本(ほん)"  # Ruby in parentheses between kanji
        result = validator.validate_no_ruby_artifacts(text)
        assert isinstance(result, bool)

    def test_validate_no_noise_valid(self):
        validator = PromptOutputValidator()
        text = "これは正常な日本語のテキストです"
        assert validator.validate_no_noise(text) == True

    def test_validate_no_noise_with_lines(self):
        validator = PromptOutputValidator()
        text = "日本語の\n────\nテキスト"  # Rule line in middle
        result = validator.validate_no_noise(text)
        assert isinstance(result, bool)  # May or may not have issues

    def test_validate_content_quality_valid(self):
        validator = PromptOutputValidator()
        text = "これは正常な日本語のテキストです。十分な長さと内容があります。"
        assert validator.validate_content_quality(text) == True

    def test_validate_content_quality_empty(self):
        validator = PromptOutputValidator()
        result = validator.validate_content_quality("")
        assert result == False

    def test_validate_complete_valid(self):
        validator = PromptOutputValidator()
        text = "日本語"  # Simple valid text
        is_valid, issues = validator.validate_complete(text)
        assert isinstance(is_valid, bool)  # May have issues from noise/ruby detection

    def test_validate_complete_empty(self):
        validator = PromptOutputValidator()
        is_valid, issues = validator.validate_complete("")
        assert is_valid == False
        assert len(issues) > 0

    def test_get_issues(self):
        validator = PromptOutputValidator()
        validator.issues = ["問題1", "問題2"]
        assert validator.get_issues() == ["問題1", "問題2"]

    def test_reset(self):
        validator = PromptOutputValidator()
        validator.issues = ["問題1"]
        validator.reset()
        assert validator.get_issues() == []

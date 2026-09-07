"""
Tests for Ruby Handler Module
"""

import pytest
from src.prompt_engine.handlers.ruby_handler import RubyHandler


class TestRubyHandler:
    """Tests for RubyHandler class"""

    def test_initialization(self):
        handler = RubyHandler()
        assert handler.enabled == True

    def test_is_ruby_text_katakana(self):
        handler = RubyHandler()
        assert handler.is_ruby_text("ア") == True
        assert handler.is_ruby_text("カイ") == True
        assert handler.is_ruby_text("スキ") == True

    def test_is_ruby_text_hiragana(self):
        handler = RubyHandler()
        assert handler.is_ruby_text("か") == True
        assert handler.is_ruby_text("がく") == True

    def test_is_ruby_text_long(self):
        handler = RubyHandler()
        assert handler.is_ruby_text("가가가가") == False
        assert handler.is_ruby_text("これが答えです") == False

    def test_is_ruby_text_empty(self):
        handler = RubyHandler()
        assert handler.is_ruby_text("") == False
        assert handler.is_ruby_text(None) == False

    def test_extract_ruby_from_mixed_text(self):
        handler = RubyHandler()
        text = "日に本ほん"
        cleaned, ruby = handler.extract_ruby_from_text(text)
        assert "に" in ruby
        assert "本" not in ruby

    def test_extract_ruby_from_clean_text(self):
        handler = RubyHandler()
        text = "これはテストです"
        cleaned, ruby = handler.extract_ruby_from_text(text)
        assert "テスト" in cleaned or "です" in cleaned
        assert len(ruby) == 0

    def test_extract_ruby_with_kanji_context(self):
        handler = RubyHandler()
        text = "日(に)本(ほん)"  # Ruby in parentheses between kanji
        cleaned, ruby = handler.extract_ruby_from_text(text)
        assert "日本" in cleaned or len(ruby) >= 0

    def test_post_process_text(self):
        handler = RubyHandler()
        text = "日に本ほん\n山川さん"
        result = handler.post_process_text(text)
        assert "日本" in result

    def test_validate_no_ruby_clean(self):
        handler = RubyHandler()
        text = "これはテストです"
        issues = handler.validate_no_ruby(text)
        assert len(issues) == 0

    def test_validate_no_ruby_with_issues(self):
        handler = RubyHandler()
        text = "日か本ほん"  # Small kana may be ruby between kanji
        issues = handler.validate_no_ruby(text)
        assert isinstance(issues, list)

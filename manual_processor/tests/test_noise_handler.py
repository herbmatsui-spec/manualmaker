"""
Tests for Noise Handler Module
"""

import pytest
from src.prompt_engine.handlers.noise_handler import NoiseHandler


class TestNoiseHandler:
    """Tests for NoiseHandler class"""

    def test_initialization(self):
        handler = NoiseHandler()
        assert handler.enabled == True
        assert handler.get_noise_count() == 0

    def test_is_noise_line_horizontal_rules(self):
        handler = NoiseHandler()
        assert handler.is_noise_line("─" * 10) == True
        assert handler.is_noise_line("━") == True
        assert handler.is_noise_line("──────") == True

    def test_is_noise_line_vertical_rules(self):
        handler = NoiseHandler()
        assert handler.is_noise_line("│") == True
        assert handler.is_noise_line("┃") == True
        assert handler.is_noise_line("|") == True

    def test_is_noise_line_dots(self):
        handler = NoiseHandler()
        assert handler.is_noise_line("・") == True
        assert handler.is_noise_line("・:;") == True
        assert handler.is_noise_line("abc") == False

    def test_is_noise_line_normal_text(self):
        handler = NoiseHandler()
        assert handler.is_noise_line("これはテストです") == False
        assert handler.is_noise_line("売上総利益") == False

    def test_is_noise_word_symbols(self):
        handler = NoiseHandler()
        assert handler.is_noise_word("─") == True
        assert handler.is_noise_word("━") == True
        assert handler.is_noise_word("│") == True
        assert handler.is_noise_word("・") == True

    def test_is_noise_word_normal(self):
        handler = NoiseHandler()
        assert handler.is_noise_word("テスト") == False
        assert handler.is_noise_word("123") == False

    def test_remove_noise_from_text(self):
        handler = NoiseHandler()
        text = "売上総利益\n─ ─ ─ ─\n仕入原価"
        result = handler.remove_noise_from_text(text)
        assert "─" not in result
        assert "売上総利益" in result
        assert "仕入原価" in result

    def test_remove_noise_count(self):
        handler = NoiseHandler()
        text = "────\n││││\n正常なテキスト"
        handler.remove_noise_from_text(text)
        assert handler.get_noise_count() >= 2

    def test_reset_noise_count(self):
        handler = NoiseHandler()
        handler._noise_count = 5
        handler.reset_noise_count()
        assert handler.get_noise_count() == 0

    def test_validate_clean_no_issues(self):
        handler = NoiseHandler()
        text = "正常な日本語のテキスト"
        issues = handler.validate_clean(text)
        assert len(issues) == 0

    def test_validate_clean_with_noise(self):
        handler = NoiseHandler()
        text = "売上総利益\n────\n仕入原価"
        issues = handler.validate_clean(text)
        assert len(issues) > 0

    def test_empty_text(self):
        handler = NoiseHandler()
        assert handler.is_noise_line("") == False
        assert handler.is_noise_line("   ") == False

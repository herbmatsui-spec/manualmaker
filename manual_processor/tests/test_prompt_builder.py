"""
Tests for Prompt Builder Module
"""

import pytest
from src.prompt_engine.prompt_builder import HandwrittenPromptBuilder, PromptConfig
from src.prompt_engine.prompt_templates import (
    LITERAL_TRANSCRIPTION_RULE,
    UNREADABLE_CHAR_RULE,
    RUBY_IGNORANCE_RULE,
    NOISE_EXCLUSION_RULE,
    DEFAULT_SYSTEM_PROMPT,
)


class TestPromptConfig:
    """Tests for PromptConfig dataclass"""

    def test_default_config(self):
        config = PromptConfig()
        assert config.layout == "horizontal"
        assert config.domain_terms == []
        assert config.has_diagrams == False
        assert config.low_quality_mode == False
        assert config.strict_mode == True

    def test_custom_config(self):
        config = PromptConfig(
            layout="vertical",
            domain_terms=["テスト", "検証"],
            has_diagrams=True,
            low_quality_mode=True,
        )
        assert config.layout == "vertical"
        assert config.domain_terms == ["テスト", "検証"]
        assert config.has_diagrams == True
        assert config.low_quality_mode == True

    def test_invalid_layout_defaults_to_horizontal(self):
        config = PromptConfig(layout="invalid")
        assert config.layout == "horizontal"


class TestHandwrittenPromptBuilder:
    """Tests for HandwrittenPromptBuilder class"""

    def test_builder_initialization(self):
        builder = HandwrittenPromptBuilder()
        assert builder.config is not None
        assert builder._rules == []

    def test_reset(self):
        builder = HandwrittenPromptBuilder()
        builder.no_summarize()
        assert len(builder._rules) > 0
        builder.reset()
        assert builder._rules == []

    def test_no_summarize(self):
        builder = HandwrittenPromptBuilder()
        builder.no_summarize()
        prompt = builder.build()
        assert LITERAL_TRANSCRIPTION_RULE in prompt

    def test_mark_unreadable_default(self):
        builder = HandwrittenPromptBuilder()
        builder.mark_unreadable()
        prompt = builder.build()
        assert "●" in prompt

    def test_mark_unreadable_custom_marker(self):
        builder = HandwrittenPromptBuilder()
        builder.mark_unreadable(marker="[読解不能]")
        prompt = builder.build()
        assert "[読解不能]" in prompt
        assert "●" not in prompt

    def test_ignore_ruby(self):
        builder = HandwrittenPromptBuilder()
        builder.ignore_ruby()
        prompt = builder.build()
        assert RUBY_IGNORANCE_RULE in prompt

    def test_exclude_noise(self):
        builder = HandwrittenPromptBuilder()
        builder.exclude_noise()
        prompt = builder.build()
        assert NOISE_EXCLUSION_RULE in prompt

    def test_set_layout_horizontal(self):
        builder = HandwrittenPromptBuilder()
        builder.set_layout("horizontal")
        prompt = builder.build()
        assert "横書き" in prompt
        assert "左から右" in prompt

    def test_set_layout_vertical(self):
        builder = HandwrittenPromptBuilder()
        builder.set_layout("vertical")
        prompt = builder.build()
        assert "縦書き" in prompt
        assert "右の行から左" in prompt

    def test_add_domain_terms(self):
        builder = HandwrittenPromptBuilder()
        builder.add_domain_terms(["専門用語1", "専門用語2"])
        prompt = builder.build()
        assert "専門用語1" in prompt
        assert "専門用語2" in prompt

    def test_structure_diagrams(self):
        builder = HandwrittenPromptBuilder()
        builder.structure_diagrams()
        prompt = builder.build()
        assert "マークダウン形式" in prompt
        assert builder.config.has_diagrams == True

    def test_handle_low_quality(self):
        builder = HandwrittenPromptBuilder()
        builder.handle_low_quality()
        prompt = builder.build()
        assert "低品質" in prompt or "薄く書かれた" in prompt
        assert builder.config.low_quality_mode == True

    def test_add_confusing_chars_warning(self):
        builder = HandwrittenPromptBuilder()
        builder.add_confusing_chars_warning()
        prompt = builder.build()
        assert "シ" in prompt
        assert "ツ" in prompt
        assert "ソ" in prompt
        assert "ン" in prompt
        assert "類似文字" in prompt

    def test_full_pipeline(self):
        builder = HandwrittenPromptBuilder()
        builder.add_header()
        builder.no_summarize()
        builder.mark_unreadable()
        builder.ignore_ruby()
        builder.exclude_noise()
        builder.set_layout("vertical")
        builder.add_domain_terms(["技術文書"])
        builder.structure_diagrams()
        builder.handle_low_quality()
        builder.add_output_format()

        prompt = builder.build()
        assert len(prompt) > 0
        assert LITERAL_TRANSCRIPTION_RULE in prompt
        assert RUBY_IGNORANCE_RULE in prompt
        assert "専門用語" in prompt

    def test_build_returns_string(self):
        builder = HandwrittenPromptBuilder()
        builder.no_summarize()
        result = builder.build()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_for_gemini(self):
        builder = HandwrittenPromptBuilder()
        builder.no_summarize()
        result = builder.build_for_gemini()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_english_prompt_uses_localized_rules(self):
        builder = HandwrittenPromptBuilder(PromptConfig(language="en"))
        prompt = builder.build_handwritten_transcription_prompt()

        assert "Strict Rules" in prompt
        assert "Complete transcription" in prompt
        assert "Ignore ruby text" in prompt
        assert "Output Format" in prompt
        assert "厳守事項" not in prompt

    def test_chinese_prompt_uses_localized_rules(self):
        builder = HandwrittenPromptBuilder(PromptConfig(language="zh"))
        prompt = builder.build_handwritten_transcription_prompt(layout="vertical")

        assert "严格规则" in prompt
        assert "完整转录" in prompt
        assert "竖排文本" in prompt
        assert "输出格式" in prompt

    def test_build_processing_context_excludes_transcription_only_rules(self):
        builder = HandwrittenPromptBuilder(PromptConfig(
            layout="vertical",
            domain_terms=["固有名詞"],
            has_diagrams=True,
            low_quality_mode=True,
        ))

        context = builder.build_processing_context()

        assert "縦書き" in context
        assert "固有名詞" in context
        assert "図解" in context
        assert "低品質画像" in context
        assert "要約、解説" not in context


class TestPromptIntegration:
    """Integration tests for prompt builder"""

    def test_handwritten_transcription_use_case(self):
        """Test the typical handwritten transcription use case"""
        config = PromptConfig(
            layout="vertical",
            domain_terms=["手書き", "文書", "読み取り"],
            has_diagrams=True,
            low_quality_mode=True,
        )
        builder = HandwrittenPromptBuilder(config)
        builder.add_header()
        builder.no_summarize()
        builder.mark_unreadable()
        builder.add_confusing_chars_warning()
        builder.ignore_ruby()
        builder.exclude_noise()
        builder.set_layout(config.layout)
        builder.add_domain_terms(config.domain_terms)
        builder.structure_diagrams()
        builder.handle_low_quality()
        builder.add_output_format()

        prompt = builder.build()

        assert "完全" in prompt
        assert "一字一句正確" in prompt
        assert "●" in prompt
        assert "ルビ" in prompt
        assert "罫線" in prompt
        assert "縦書き" in prompt
        assert "手書き" in prompt
        assert "マークダウン形式" in prompt
        assert "シ" in prompt
        assert "ツ" in prompt

    def test_empty_builder_returns_warning(self):
        """Test that building without rules logs a warning"""
        builder = HandwrittenPromptBuilder()
        prompt = builder.build()
        assert prompt == ""

    def test_build_handwritten_transcription_prompt(self):
        builder = HandwrittenPromptBuilder()
        prompt = builder.build_handwritten_transcription_prompt(
            layout="vertical",
            domain_terms=["手書き文書"],
            has_diagrams=True,
            low_quality=True,
        )

        assert "一字一句正確" in prompt
        assert "推測・補完しない" in prompt
        assert "ルビ" in prompt
        assert "罫線" in prompt
        assert "縦書き" in prompt
        assert "手書き文書" in prompt
        assert "マークダウン形式" in prompt
        assert "薄く書かれた文字" in prompt

    def test_build_handwritten_transcription_prompt_is_repeatable(self):
        builder = HandwrittenPromptBuilder()
        first = builder.build_handwritten_transcription_prompt()
        second = builder.build_handwritten_transcription_prompt()

        assert first == second

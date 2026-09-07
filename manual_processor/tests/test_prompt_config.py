"""Tests for AppConfig and prompt builder integration."""

from config.config import AppConfig
from src.prompt_engine.prompt_builder import HandwrittenPromptBuilder
from src.exceptions import PromptEngineError
from src.cache_manager import CacheManager


def test_builder_reads_prompt_settings_from_config():
    app_config = AppConfig(
        google_cloud_project_id="project",
        vision_api=False,
        google_application_credentials="",
        prompt_layout="vertical",
        prompt_domain_terms=["固有名詞"],
        prompt_has_diagrams=True,
        prompt_low_quality_mode=True,
        prompt_strict_mode=True,
    )

    prompt = HandwrittenPromptBuilder.from_config(app_config).build_handwritten_transcription_prompt()

    assert "縦書き" in prompt
    assert "固有名詞" in prompt
    assert "薄く書かれた文字" in prompt


def test_prompt_settings_are_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("PROMPT_LAYOUT", "vertical")
    monkeypatch.setenv("PROMPT_DOMAIN_TERMS", "用語A, 用語B")
    monkeypatch.setenv("PROMPT_HAS_DIAGRAMS", "true")
    monkeypatch.setenv("PROMPT_LOW_QUALITY_MODE", "1")

    config = AppConfig.from_env()

    assert config.prompt_layout == "vertical"
    assert config.prompt_domain_terms == ["用語A", "用語B"]
    assert config.prompt_has_diagrams is True
    assert config.prompt_low_quality_mode is True


def test_custom_prompt_rules_are_loaded_and_added(monkeypatch):
    monkeypatch.setenv("PROMPT_CUSTOM_RULES", "社内用語は原文表記を維持\n空行を保持する")

    config = AppConfig.from_env()
    prompt = HandwrittenPromptBuilder.from_config(config).build_handwritten_transcription_prompt()

    assert config.prompt_custom_rules == ["社内用語は原文表記を維持", "空行を保持する"]
    assert "社内用語は原文表記を維持" in prompt
    assert "空行を保持する" in prompt


def test_default_language_is_used_by_prompt_builder(monkeypatch):
    monkeypatch.setenv("APP_LANGUAGE", "en")

    config = AppConfig.from_env()
    prompt = HandwrittenPromptBuilder.from_config(config).build_handwritten_transcription_prompt()

    assert "Strict Rules" in prompt
    assert "Complete transcription" in prompt


def test_invalid_custom_prompt_rule_raises_domain_error():
    builder = HandwrittenPromptBuilder()

    try:
        builder.add_custom_rules([123])
    except PromptEngineError as error:
        assert error.error_code == "INVALID_CUSTOM_PROMPT_RULE"
    else:
        raise AssertionError("PromptEngineError was not raised")


def test_prompt_builder_reuses_cached_prompt(tmp_path):
    cache = CacheManager(cache_dir=tmp_path / "cache")
    builder = HandwrittenPromptBuilder(cache_manager=cache)

    first = builder.build_handwritten_transcription_prompt(
        layout="vertical", domain_terms=["用語"]
    )
    builder.reset()
    second = builder.build_handwritten_transcription_prompt(
        layout="vertical", domain_terms=["用語"]
    )

    assert first == second
    assert cache.get(builder._prompt_cache_key("vertical", ["用語"], False, False)) == {
        "prompt": first
    }

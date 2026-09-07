"""
Tests for Advanced Features (Steps 10 - 18)
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from config.config import AppConfig
from src.processor.processor_factory import ProcessorFactory, LocalProcessor, HybridProcessor
from src.plugins.output_plugin import BaseOutputGenerator, PluginRegistry
from src.progress_manager import CancellationToken, ProgressTracker, OperationCancelledError
from src.batch_processor import BatchProcessor
from src.i18n_manager import I18nManager
from src.cache_manager import CacheManager
from src.security_manager import SecurityManager


class DummyPlugin(BaseOutputGenerator):
    @property
    def format_name(self) -> str:
        return "custom"

    def generate(self, summary_result, output_dir, filename_prefix, **kwargs):
        out = output_dir / f"{filename_prefix}.custom"
        out.touch()
        return out


def test_processor_factory_local():
    config = AppConfig(google_cloud_project_id="test", vision_api=False, google_application_credentials="dummy", processor_type="local")
    proc = ProcessorFactory.create_processor(config)
    assert isinstance(proc, LocalProcessor)
    res = proc.process_document("テストテキスト\n2行目")
    assert res.title == "ローカル要約マニュアル"


def test_plugin_registry(tmp_path):
    plugin = DummyPlugin()
    PluginRegistry.register(plugin)
    assert "custom" in PluginRegistry.list_formats()

    mock_result = Mock()
    res = PluginRegistry.generate_outputs(mock_result, tmp_path, "test_file", enabled_formats=["custom"])
    assert "custom" in res
    assert res["custom"].exists()


def test_cancellation_token():
    token = CancellationToken()
    assert not token.is_cancelled
    token.cancel()
    assert token.is_cancelled
    with pytest.raises(OperationCancelledError):
        token.throwIfCancelled()


def test_i18n_manager():
    i18n = I18nManager()
    assert i18n.get_text("summary_title", "ja") == "マニュアル概要"
    assert i18n.get_text("summary_title", "en") == "Manual Summary"
    assert i18n.detect_language("こんにちは世界") == "ja"
    assert i18n.detect_language("Hello World") == "en"

    i18n.set_language("en")
    assert i18n.current_lang == "en"
    i18n.set_language("invalid_lang")
    assert i18n.current_lang == "ja"

    assert "ja" in i18n.get_available_languages()
    assert "en" in i18n.get_available_languages()
    assert "zh" in i18n.get_available_languages()
    assert "ko" in i18n.get_available_languages()
    assert "es" in i18n.get_available_languages()

    assert i18n.detect_language("这是中文文本") == "zh"
    assert i18n.detect_language("이것은 한국어") == "ko"

    i18n.set_language("ja")
    assert i18n.get_text("button_ok") == "OK"
    i18n.set_language("es")
    assert i18n.get_text("button_ok") == "Aceptar"


def test_cache_manager(tmp_path):
    cache = CacheManager(cache_dir=tmp_path / "cache")
    text = "テストキャッシュコンテンツ"
    data = {"summary": "Cached Summary"}
    cache.set(text, data)
    retrieved = cache.get(text)
    assert retrieved == data


def test_batch_processor_shares_prompt_builder():
    from src.batch_processor import BatchProcessor
    from src.prompt_engine.prompt_builder import HandwrittenPromptBuilder

    processor = Mock()
    processor.prompt_builder = HandwrittenPromptBuilder()
    batch = BatchProcessor(processor)

    assert batch.prompt_builder is processor.prompt_builder
    assert "OCR" in batch.get_prompt_context()


def test_cli_prompt_options_update_config():
    from argparse import Namespace
    from main import apply_prompt_cli_options

    config = AppConfig(
        google_cloud_project_id="test",
        vision_api=False,
        google_application_credentials="dummy",
    )
    args = Namespace(
        prompt_layout="vertical",
        prompt_strict=True,
        prompt_no_diagrams=True,
        prompt_domain_terms="用語A, 用語B",
    )

    apply_prompt_cli_options(config, args)

    assert config.prompt_layout == "vertical"
    assert config.prompt_strict_mode is True
    assert config.prompt_has_diagrams is False
    assert config.prompt_domain_terms == ["用語A", "用語B"]


def test_security_manager():
    sensitive = "連絡先: 090-1234-5678, メール: user@example.com"
    masked, info = SecurityManager.mask_sensitive_data(sensitive, record_positions=True)
    assert "[REDACTED_PHONE]" in masked
    assert "[REDACTED_EMAIL]" in masked
    assert info["counts"].get("PHONE") == 1
    assert info["counts"].get("EMAIL") == 1

    assert "positions" in info
    assert len(info["positions"]) == 2

    sensitive2 = "マイナンバー: 1234-5678-9012"
    masked2, info2 = SecurityManager.mask_sensitive_data(sensitive2)
    assert "[REDACTED_MYNUMBER]" in masked2
    assert info2["counts"].get("MY_NUMBER") == 1

    sensitive3 = "パスポート: AB1234567"
    masked3, info3 = SecurityManager.mask_sensitive_data(sensitive3)
    assert "[REDACTED_PASSPORT]" in masked3
    assert info3["counts"].get("PASSPORT") == 1


def test_security_manager_unmask():
    original = "メール: test@example.com"
    masked, info = SecurityManager.mask_sensitive_data(original, record_positions=True)
    positions = info.get("positions", [])
    original_values = ["test@example.com"]

    unmasked = SecurityManager.unmask_data(masked, positions, original_values)
    assert "test@example.com" in unmasked


def test_audit_logger():
    from src.security_manager import AuditLogger
    audit = AuditLogger()
    audit.log("user123", "TEST_ACTION", "/test/resource", "Test details")
    logs = audit.get_recent_logs(limit=10)
    assert len(logs) >= 1
    assert logs[-1]["user_id"] == "user123"
    assert logs[-1]["action"] == "TEST_ACTION"


def test_gdpr_manager():
    from src.security_manager import GDPRManager
    GDPRManager.register_data("user_test", "profile", {"name": "Test User"})
    exported = GDPRManager.export_user_data("user_test")
    assert exported["user_id"] == "user_test"
    assert "profile" in exported["exported_data"]

    result = GDPRManager.delete_user_data("user_test")
    assert result is True

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


def test_cache_manager(tmp_path):
    cache = CacheManager(cache_dir=tmp_path / "cache")
    text = "テストキャッシュコンテンツ"
    data = {"summary": "Cached Summary"}
    cache.set(text, data)
    retrieved = cache.get(text)
    assert retrieved == data


def test_security_manager():
    sensitive = "連絡先: 090-1234-5678, メール: user@example.com"
    masked, counts = SecurityManager.mask_sensitive_data(sensitive)
    assert "[REDACTED_PHONE]" in masked
    assert "[REDACTED_EMAIL]" in masked
    assert counts.get("PHONE") == 1
    assert counts.get("EMAIL") == 1

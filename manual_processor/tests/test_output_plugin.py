"""
Tests for output_plugin module (Step 18)
Target coverage: 95%
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from abc import ABC

from src.plugins.output_plugin import (
    BaseOutputGenerator,
    PluginRegistry,
)


class DummyPlugin(BaseOutputGenerator):
    @property
    def format_name(self) -> str:
        return "dummy"

    def generate(self, summary_result, output_dir, filename_prefix, **kwargs):
        out = output_dir / f"{filename_prefix}.dummy"
        out.touch()
        return out


class AnotherPlugin(BaseOutputGenerator):
    @property
    def format_name(self) -> str:
        return "another"

    def generate(self, summary_result, output_dir, filename_prefix, **kwargs):
        return None


class FailingPlugin(BaseOutputGenerator):
    @property
    def format_name(self) -> str:
        return "failing"

    def generate(self, summary_result, output_dir, filename_prefix, **kwargs):
        raise Exception("Plugin generation failed")


class TestBaseOutputGenerator:
    """Test BaseOutputGenerator abstract class"""

    def test_is_abstract(self):
        with pytest.raises(TypeError):
            BaseOutputGenerator()

    def test_subclass_must_implement_format_name(self):
        class IncompletePlugin(BaseOutputGenerator):
            def generate(self, summary_result, output_dir, filename_prefix, **kwargs):
                pass

        with pytest.raises(TypeError):
            IncompletePlugin()

    def test_subclass_must_implement_generate(self):
        class IncompletePlugin(BaseOutputGenerator):
            @property
            def format_name(self):
                return "incomplete"

        with pytest.raises(TypeError):
            IncompletePlugin()


class TestPluginRegistry:
    """Test PluginRegistry class"""

    def setup_method(self):
        PluginRegistry._plugins.clear()

    def teardown_method(self):
        PluginRegistry._plugins.clear()

    def test_register_plugin(self):
        plugin = DummyPlugin()
        PluginRegistry.register(plugin)
        assert "dummy" in PluginRegistry.list_formats()

    def test_register_case_insensitive(self):
        class UpperCasePlugin(BaseOutputGenerator):
            @property
            def format_name(self) -> str:
                return "UPPERCASE"

            def generate(self, summary_result, output_dir, filename_prefix, **kwargs):
                pass

        plugin = UpperCasePlugin()
        PluginRegistry.register(plugin)
        assert "uppercase" in PluginRegistry.list_formats()

    def test_get_plugin_existing(self):
        plugin = DummyPlugin()
        PluginRegistry.register(plugin)
        retrieved = PluginRegistry.get_plugin("dummy")
        assert retrieved is plugin

    def test_get_plugin_case_insensitive(self):
        plugin = DummyPlugin()
        PluginRegistry.register(plugin)
        retrieved = PluginRegistry.get_plugin("DUMMY")
        assert retrieved is plugin

    def test_get_plugin_nonexistent(self):
        retrieved = PluginRegistry.get_plugin("nonexistent")
        assert retrieved is None

    def test_list_formats_empty(self):
        formats = PluginRegistry.list_formats()
        assert isinstance(formats, list)

    def test_list_formats_multiple(self):
        plugin1 = DummyPlugin()
        plugin2 = AnotherPlugin()
        PluginRegistry.register(plugin1)
        PluginRegistry.register(plugin2)
        formats = PluginRegistry.list_formats()
        assert "dummy" in formats
        assert "another" in formats

    def test_generate_outputs_with_enabled_formats(self, tmp_path):
        plugin = DummyPlugin()
        PluginRegistry.register(plugin)
        mock_result = Mock()

        results = PluginRegistry.generate_outputs(
            mock_result, tmp_path, "test", enabled_formats=["dummy"]
        )
        assert "dummy" in results
        assert results["dummy"].exists()

    def test_generate_outputs_without_enabled_formats_uses_all(self, tmp_path):
        plugin1 = DummyPlugin()
        plugin2 = AnotherPlugin()
        PluginRegistry.register(plugin1)
        PluginRegistry.register(plugin2)

        mock_result = Mock()
        results = PluginRegistry.generate_outputs(mock_result, tmp_path, "test")
        assert "dummy" in results
        assert "another" not in results

    def test_generate_outputs_plugin_returns_none(self, tmp_path):
        plugin = AnotherPlugin()
        PluginRegistry.register(plugin)
        mock_result = Mock()

        results = PluginRegistry.generate_outputs(
            mock_result, tmp_path, "test", enabled_formats=["another"]
        )
        assert "another" not in results

    def test_generate_outputs_plugin_exception(self, tmp_path, caplog):
        import logging
        caplog.set_level(logging.ERROR)

        plugin = FailingPlugin()
        PluginRegistry.register(plugin)
        mock_result = Mock()

        results = PluginRegistry.generate_outputs(
            mock_result, tmp_path, "test", enabled_formats=["failing"]
        )
        assert "failing" not in results
        assert "Failed to generate" in caplog.text

    def test_generate_outputs_no_plugin_registered(self, tmp_path, caplog):
        import logging
        caplog.set_level(logging.WARNING)

        mock_result = Mock()
        results = PluginRegistry.generate_outputs(
            mock_result, tmp_path, "test", enabled_formats=["notregistered"]
        )
        assert "notregistered" not in results
        assert "No plugin registered" in caplog.text

    def test_generate_outputs_with_kwargs(self, tmp_path):
        class KwargPlugin(BaseOutputGenerator):
            @property
            def format_name(self) -> str:
                return "kwarg"

            def generate(self, summary_result, output_dir, filename_prefix, **kwargs):
                if kwargs.get("create_file"):
                    out = output_dir / f"{filename_prefix}.kwarg"
                    out.touch()
                    return out
                return None

        plugin = KwargPlugin()
        PluginRegistry.register(plugin)
        mock_result = Mock()

        results = PluginRegistry.generate_outputs(
            mock_result, tmp_path, "test", enabled_formats=["kwarg"], create_file=True
        )
        assert "kwarg" in results

    def test_generate_outputs_empty_enabled_formats(self, tmp_path):
        mock_result = Mock()
        results = PluginRegistry.generate_outputs(
            mock_result, tmp_path, "test", enabled_formats=[]
        )
        assert len(results) == 0

    def test_generate_outputs_multiple_plugins_same_format(self, tmp_path):
        plugin1 = DummyPlugin()
        PluginRegistry.register(plugin1)
        plugin2 = DummyPlugin()
        PluginRegistry.register(plugin2)

        mock_result = Mock()
        results = PluginRegistry.generate_outputs(
            mock_result, tmp_path, "test", enabled_formats=["dummy"]
        )
        assert "dummy" in results

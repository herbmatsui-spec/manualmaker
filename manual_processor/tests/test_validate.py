"""Tests for config/validate.py"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestValidateConfigFile:
    """Tests for validate_config_file()"""

    def test_file_not_found_returns_1(self):
        from config.validate import validate_config_file

        result = validate_config_file(Path("/nonexistent/config.yaml"))
        assert result == 1

    def test_valid_config_returns_0(self, tmp_path):
        from config.validate import validate_config_file

        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
app:
  name: test-app
web:
  port: 8000
""")
        result = validate_config_file(config_file)
        assert result == 0

    def test_load_settings_exception_returns_1(self, tmp_path, monkeypatch):
        from config.validate import validate_config_file
        from pydantic import ValidationError

        config_file = tmp_path / "config.yaml"
        config_file.write_text("app:\n  name: test\n")

        def fake_load_settings(path=None):
            raise RuntimeError("config error")

        monkeypatch.setattr("config.validate.load_settings", fake_load_settings)
        result = validate_config_file(config_file)
        assert result == 1


class TestValidateCurrentConfig:
    """Tests for validate_current_config()"""

    def test_valid_current_config_returns_0(self):
        from config.validate import validate_current_config

        result = validate_current_config()
        assert result == 0

    def test_load_settings_exception_returns_1(self, monkeypatch):
        from config.validate import validate_current_config

        def fake_load_settings(path=None):
            raise RuntimeError("config error")

        monkeypatch.setattr("config.validate.load_settings", fake_load_settings)
        result = validate_current_config()
        assert result == 1


class TestMain:
    """Tests for main() entry point"""

    def test_main_no_args_calls_validate_current_config(self, monkeypatch):
        from config.validate import main

        called = False
        def fake_validate_current():
            nonlocal called
            called = True
            return 0
        monkeypatch.setattr("config.validate.validate_current_config", fake_validate_current)
        result = main([])
        assert called
        assert result == 0

    def test_main_with_path_calls_validate_config_file(self, tmp_path, monkeypatch):
        from config.validate import main

        config_file = tmp_path / "config.yaml"
        config_file.write_text("app:\n  name: x\n")
        called_path = None
        def fake_validate(path):
            nonlocal called_path
            called_path = path
            return 0
        monkeypatch.setattr("config.validate.validate_config_file", fake_validate)
        result = main([str(config_file)])
        assert called_path == config_file
        assert result == 0

    def test_main_with_invalid_config_returns_1(self, tmp_path, monkeypatch):
        from config.validate import main

        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: content: [")
        monkeypatch.setattr("config.validate.validate_config_file", lambda p: 1)
        result = main([str(config_file)])
        assert result == 1

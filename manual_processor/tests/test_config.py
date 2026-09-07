"""
Tests for configuration system.
"""

import os
import tempfile
import pytest
from pathlib import Path
import yaml

from config.settings import Settings, AppSettings, WebSettings, OCRSettings
from config.loader import load_settings, find_config_file, _deep_merge
from config.validate import validate_config_file, validate_current_config


class TestSettingsModels:
    """Test Pydantic settings models"""

    def test_default_settings(self):
        """Test default settings values"""
        settings = Settings()
        assert settings.app.name == "manual-processor"
        assert settings.app.version == "2.1.0"
        assert settings.web.port == 8000
        assert settings.web.cors_origins == ["http://localhost:3000", "http://localhost:8000"]
        assert settings.ocr.provider == "google_vision"
        assert settings.gemini.temperature == 0.3

    def test_web_port_validation(self):
        """Test web port range validation"""
        with pytest.raises(Exception):  # ValidationError
            WebSettings(port=99999)

    def test_ocr_provider_validation(self):
        """Test OCR provider validation"""
        with pytest.raises(Exception):  # ValidationError
            OCRSettings(provider="invalid_provider")

    def test_gemini_temperature_validation(self):
        """Test Gemini temperature range validation"""
        with pytest.raises(Exception):  # ValidationError
            Settings(gemini={"temperature": 2.0})

    def test_nested_settings(self):
        """Test nested settings access"""
        settings = Settings()
        assert settings.security.pii_masking.enabled is False
        assert settings.security.audit.retention_days == 90


class TestConfigLoader:
    """Test configuration loader"""

    def test_load_default_settings(self):
        """Test loading default settings"""
        settings = load_settings()
        assert isinstance(settings, Settings)
        assert settings.app.name == "manual-processor"

    def test_load_from_yaml_file(self):
        """Test loading settings from YAML file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "app": {"name": "test-app", "debug": True},
                "web": {"port": 9000}
            }, f)
            config_path = f.name

        try:
            settings = load_settings(Path(config_path))
            assert settings.app.name == "test-app"
            assert settings.app.debug is True
            assert settings.web.port == 9000
        finally:
            os.unlink(config_path)

    def test_env_override(self):
        """Test environment variable override"""
        os.environ["WEB_PORT"] = "7777"
        os.environ["APP_DEBUG"] = "true"
        
        try:
            settings = load_settings()
            assert settings.web.port == 7777
            assert settings.app.debug is True
        finally:
            del os.environ["WEB_PORT"]
            del os.environ["APP_DEBUG"]

    def test_find_config_file(self):
        """Test config file discovery"""
        # Should find config.example.yaml
        config_path = find_config_file()
        if config_path:
            assert config_path.exists()

    def test_deep_merge(self):
        """Test deep merge utility"""
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 4}, "e": 5}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": {"c": 4, "d": 3}, "e": 5}


class TestConfigValidation:
    """Test configuration validation"""

    def test_validate_valid_config(self, tmp_path):
        """Test validating a valid config file"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
app:
  name: test-app
web:
  port: 8000
""")
        assert validate_config_file(config_file) == 0

    def test_validate_missing_file(self):
        """Test validating missing config file"""
        assert validate_config_file(Path("/nonexistent/config.yaml")) == 1

    def test_validate_current_config(self):
        """Test validating current configuration"""
        # Should not raise
        assert validate_current_config() == 0


class TestConfigIntegration:
    """Integration tests for config system"""

    def test_yaml_and_env_merge(self):
        """Test YAML config merged with env vars"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"web": {"port": 8000}}, f)
            config_path = f.name

        os.environ["WEB_PORT"] = "9000"
        
        try:
            settings = load_settings(Path(config_path))
            # Env should override YAML
            assert settings.web.port == 9000
        finally:
            os.unlink(config_path)
            del os.environ["WEB_PORT"]

    def test_config_reload(self):
        """Test config reload with different files"""
        settings1 = load_settings()
        original_name = settings1.app.name
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"app": {"name": "reloaded-app"}}, f)
            config_path = f.name

        try:
            settings2 = load_settings(Path(config_path))
            assert settings2.app.name == "reloaded-app"
        finally:
            os.unlink(config_path)

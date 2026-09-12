"""
Tests for configuration system.
"""

import os
import logging
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


class TestAppConfigSetters:
    """Test AppConfig setter pathways"""

    def test_prompt_layout_setter(self):
        """Test prompt_layout setter updates settings"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        config.prompt_layout = "vertical"
        assert config.prompt_layout == "vertical"

    def test_prompt_domain_terms_setter(self):
        """Test prompt_domain_terms setter updates settings"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        test_terms = ["term1", "term2", "term3"]
        config.prompt_domain_terms = test_terms
        assert config.prompt_domain_terms == test_terms

    def test_prompt_has_diagrams_setter(self):
        """Test prompt_has_diagrams setter updates settings"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        config.prompt_has_diagrams = True
        assert config.prompt_has_diagrams is True
        config.prompt_has_diagrams = False
        assert config.prompt_has_diagrams is False

    def test_output_directory_setter(self):
        """Test output_directory setter updates settings"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        config.output_directory = Path("/tmp/test_output")
        assert config.output_directory == Path("/tmp/test_output")


class TestAppConfigFromEnv:
    """Test AppConfig.from_env() with environment variables"""

    def test_from_env_basic(self):
        """Test from_env creates AppConfig instance"""
        from config.config import AppConfig
        AppConfig._instance = None
        config = AppConfig.from_env()
        assert isinstance(config, AppConfig)
        AppConfig._instance = None

    def test_from_env_google_cloud_project_id(self, monkeypatch):
        """Test GOOGLE_CLOUD_PROJECT_ID env var"""
        from config.config import AppConfig
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "test-project-123")
        AppConfig._instance = None
        config = AppConfig.from_env()
        assert config.google_cloud_project_id == "test-project-123"
        AppConfig._instance = None

    def test_from_env_vision_api_true(self, monkeypatch):
        """Test VISION_API=true env var"""
        from config.config import AppConfig
        monkeypatch.setenv("VISION_API", "true")
        AppConfig._instance = None
        config = AppConfig.from_env()
        assert config.vision_api is True
        AppConfig._instance = None

    def test_from_env_vision_api_false(self, monkeypatch):
        """Test VISION_API=false env var"""
        from config.config import AppConfig
        monkeypatch.setenv("VISION_API", "false")
        AppConfig._instance = None
        config = AppConfig.from_env()
        assert config.vision_api is False
        AppConfig._instance = None

    def test_from_env_google_application_credentials(self, monkeypatch):
        """Test GOOGLE_APPLICATION_CREDENTIALS env var"""
        from config.config import AppConfig
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/path/to/creds.json")
        AppConfig._instance = None
        config = AppConfig.from_env()
        assert config.google_application_credentials == "/path/to/creds.json"
        AppConfig._instance = None

    def test_from_env_gemini_api_key_legacy(self, monkeypatch):
        """Test legacy GEMINI_API_KEY env var"""
        from config.config import AppConfig
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
        AppConfig._instance = None
        config = AppConfig.from_env()
        assert config.vision_api is True
        AppConfig._instance = None

    def test_from_env_app_language(self, monkeypatch):
        """Test APP_LANGUAGE env var"""
        from config.config import AppConfig
        monkeypatch.setenv("APP_LANGUAGE", "en")
        AppConfig._instance = None
        config = AppConfig.from_env()
        assert config.default_language == "en"
        AppConfig._instance = None

    def test_from_env_pdf_dpi(self, monkeypatch):
        """Test PDF_DPI env var"""
        from config.config import AppConfig
        monkeypatch.setenv("PDF_DPI", "150")
        AppConfig._instance = None
        config = AppConfig.from_env()
        assert config.pdf_dpi == 150
        AppConfig._instance = None

    def test_from_env_max_file_size_mb(self, monkeypatch):
        """Test MAX_FILE_SIZE_MB env var"""
        from config.config import AppConfig
        monkeypatch.setenv("MAX_FILE_SIZE_MB", "100")
        AppConfig._instance = None
        config = AppConfig.from_env()
        assert config.max_file_size_mb == 100
        AppConfig._instance = None

    def test_from_env_supported_extensions(self, monkeypatch):
        """Test SUPPORTED_EXTENSIONS env var"""
        from config.config import AppConfig
        monkeypatch.setenv("SUPPORTED_EXTENSIONS", ".pdf,.doc,.docx")
        AppConfig._instance = None
        config = AppConfig.from_env()
        assert config.supported_extensions == [".pdf", ".doc", ".docx"]
        AppConfig._instance = None

    def test_get_instance(self):
        """Test get_instance returns singleton"""
        from config.config import AppConfig
        AppConfig._instance = None
        config1 = AppConfig.get_instance()
        config2 = AppConfig.get_instance()
        assert config1 is config2
        AppConfig._instance = None


class TestAppConfigProperties:
    """Test AppConfig property getters"""

    def test_vision_api_timeout(self):
        """Test vision_api_timeout property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.vision_api_timeout, int)

    def test_vision_max_results(self):
        """Test vision_max_results property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.vision_max_results, int)

    def test_gemini_model_name(self):
        """Test gemini_model_name property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.gemini_model_name, str)

    def test_gemini_temperature(self):
        """Test gemini_temperature property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.gemini_temperature, float)

    def test_gemini_max_output_tokens(self):
        """Test gemini_max_output_tokens property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.gemini_max_output_tokens, int)

    def test_chunk_size(self):
        """Test chunk_size property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.chunk_size, int)

    def test_chunk_overlap(self):
        """Test chunk_overlap property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.chunk_overlap, int)

    def test_processor_type(self):
        """Test processor_type property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.processor_type, str)

    def test_fallback_enabled(self):
        """Test fallback_enabled property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.fallback_enabled, bool)

    def test_web_host(self):
        """Test web_host property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.web_host, str)

    def test_web_port(self):
        """Test web_port property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.web_port, int)

    def test_web_cors_origins(self):
        """Test web_cors_origins property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.web_cors_origins, list)

    def test_web_upload_max_mb(self):
        """Test web_upload_max_mb property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.web_upload_max_mb, int)

    def test_prompt_low_quality_mode(self):
        """Test prompt_low_quality_mode property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.prompt_low_quality_mode, bool)

    def test_prompt_strict_mode(self):
        """Test prompt_strict_mode property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.prompt_strict_mode, bool)

    def test_prompt_custom_rules(self):
        """Test prompt_custom_rules property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.prompt_custom_rules, list)

    def test_generate_diagram(self):
        """Test generate_diagram property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.generate_diagram, bool)

    def test_generate_diagram_png(self):
        """Test generate_diagram_png property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.generate_diagram_png, bool)

    def test_generate_diagram_markdown(self):
        """Test generate_diagram_markdown property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.generate_diagram_markdown, bool)

    def test_generate_diagram_mermaid(self):
        """Test generate_diagram_mermaid property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.generate_diagram_mermaid, bool)

    def test_tts_language_code(self):
        """Test tts_language_code property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.tts_language_code, str)

    def test_tts_voice_name(self):
        """Test tts_voice_name property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.tts_voice_name, str)

    def test_tts_speaking_rate(self):
        """Test tts_speaking_rate property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.tts_speaking_rate, float)

    def test_tts_pitch(self):
        """Test tts_pitch property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.tts_pitch, float)

    def test_usb_monitor_paths(self):
        """Test usb_monitor_paths property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.usb_monitor_paths, list)

    def test_usb_auto_detect(self):
        """Test usb_auto_detect property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.usb_auto_detect, bool)

    def test_usb_poll_interval(self):
        """Test usb_poll_interval property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.usb_poll_interval, (int, float))

    def test_temp_directory(self):
        """Test temp_directory property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.temp_directory, Path)

    def test_pii_masking_enabled(self):
        """Test pii_masking_enabled property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.pii_masking_enabled, bool)

    def test_google_api_key(self):
        """Test google_api_key property returns empty string"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert config.google_api_key == ""

    def test_gemini_api_key(self):
        """Test gemini_api_key property returns empty string"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert config.gemini_api_key == ""

    def test_ocr_model(self):
        """Test ocr_model property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.ocr_model, str)

    def test_summary_model(self):
        """Test summary_model property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert isinstance(config.summary_model, str)

    def test_tts_model(self):
        """Test tts_model property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert config.tts_model == "gemini-2.5-flash-tts"

    def test_tts_fallback_model(self):
        """Test tts_fallback_model property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert config.tts_fallback_model == "gemini-3.1-flash-tts"

    def test_compact_layout(self):
        """Test compact_layout property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert config.compact_layout is False

    def test_use_emojis(self):
        """Test use_emojis property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert config.use_emojis is False

    def test_diagram_theme(self):
        """Test diagram_theme property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert config.diagram_theme == "default"

    def test_diagram_width(self):
        """Test diagram_width property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert config.diagram_width == 800

    def test_diagram_height(self):
        """Test diagram_height property"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        assert config.diagram_height == 600


class TestAppConfigValidate:
    """Test AppConfig.validate() method"""

    def test_validate_returns_list(self):
        """Test validate returns a list"""
        from config.config import AppConfig
        config = AppConfig.from_env()
        result = config.validate()
        assert isinstance(result, list)

    def test_validate_with_valid_config(self, monkeypatch):
        """Test validate with proper config"""
        from config.config import AppConfig
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "test-project")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/path/to/creds")
        monkeypatch.setenv("OUTPUT_DIRECTORY", "/tmp/output")
        monkeypatch.setenv("TEMP_DIRECTORY", "/tmp/temp")
        AppConfig._instance = None
        config = AppConfig.from_env()
        errors = config.validate()
        assert isinstance(errors, list)
        AppConfig._instance = None


class TestAppConfigEnsureDirectories:
    """Test AppConfig.ensure_directories() method"""

    def test_ensure_directories_creates_dirs(self, tmp_path):
        """Test ensure_directories creates directories"""
        from config.config import AppConfig
        output_dir = tmp_path / "output"
        temp_dir = tmp_path / "temp"
        AppConfig._instance = None
        config = AppConfig.from_env()
        config._settings.paths.output_directory = str(output_dir)
        config._settings.paths.temp_directory = str(temp_dir)
        config.ensure_directories()
        assert output_dir.exists()
        assert temp_dir.exists()
        AppConfig._instance = None


class TestLoaderEnvMapping:
    """Test _env_to_settings_mapping() full coverage via load_settings()"""

    ENV_VARS = {
        "APP_DEBUG": "true",
        "OUTPUT_DIRECTORY": "/tmp/out",
        "TEMP_DIRECTORY": "/tmp/tmpdir",
        "LOG_DIRECTORY": "/tmp/logs",
        "OCR_PROVIDER": "gemini",
        "OCR_BATCH_SIZE": "5",
        "OCR_TIMEOUT": "60",
        "GEMINI_MODEL": "gemini-pro-x",
        "GEMINI_TEMPERATURE": "0.7",
        "GEMINI_MAX_TOKENS": "2048",
        "PROCESSOR_TYPE": "gemini",
        "CHUNK_SIZE": "1500",
        "WEB_HOST": "0.0.0.0",
        "WEB_PORT": "8888",
        "WEB_CORS_ORIGINS": "http://a.com, http://b.com",
        "WEB_UPLOAD_MAX_MB": "100",
        "PROMPT_LAYOUT": "vertical",
        "PROMPT_STRICT_MODE": "yes",
        "PROMPT_HAS_DIAGRAMS": "1",
        "PROMPT_LOW_QUALITY_MODE": "true",
        "PROMPT_DOMAIN_TERMS": "termA\n termB ,termC",
        "PROMPT_CUSTOM_RULES": "rule1\nrule2",
        "TTS_LANGUAGE": "en-US",
        "TTS_VOICE": "en-US-Test",
        "PII_MASKING_ENABLED": "true",
        "AUDIT_ENABLED": "false",
        "USB_AUTO_DETECT": "no",
    }

    def test_all_env_mappings(self, monkeypatch):
        """All environment variable branches in _env_to_settings_mapping"""
        for k, v in self.ENV_VARS.items():
            monkeypatch.setenv(k, v)
        settings = load_settings()
        assert settings.app.debug is True
        assert settings.paths.output_directory == "/tmp/out"
        assert settings.paths.temp_directory == "/tmp/tmpdir"
        assert settings.paths.log_directory == "/tmp/logs"
        assert settings.ocr.provider == "gemini"
        assert settings.ocr.batch_size == 5
        assert settings.ocr.timeout_seconds == 60
        assert settings.gemini.model == "gemini-pro-x"
        assert settings.gemini.temperature == 0.7
        assert settings.gemini.max_output_tokens == 2048
        assert settings.processing.processor_type == "gemini"
        assert settings.processing.chunk_size == 1500
        assert settings.web.host == "0.0.0.0"
        assert settings.web.port == 8888
        assert settings.web.cors_origins == ["http://a.com", "http://b.com"]
        assert settings.web.upload_max_mb == 100
        assert settings.prompt.layout == "vertical"
        assert settings.prompt.strict_mode is True
        assert settings.prompt.has_diagrams is True
        assert settings.prompt.low_quality_mode is True
        assert settings.prompt.domain_terms == ["termA", "termB", "termC"]
        assert settings.prompt.custom_rules == ["rule1", "rule2"]
        assert settings.tts.language_code == "en-US"
        assert settings.tts.voice_name == "en-US-Test"
        assert settings.security.pii_masking.enabled is True
        assert settings.security.audit.enabled is False
        assert settings.usb.auto_detect is False

    def test_empty_cors_origins_ignored(self, monkeypatch):
        """WEB_CORS_ORIGINS with only whitespace should not override"""
        monkeypatch.setenv("WEB_CORS_ORIGINS", " , ")
        settings = load_settings()
        assert settings.web.cors_origins == [
            "http://localhost:3000",
            "http://localhost:8000",
        ]

    def test_empty_domain_terms_ignored(self, monkeypatch):
        """PROMPT_DOMAIN_TERMS with only whitespace should not override"""
        monkeypatch.setenv("PROMPT_DOMAIN_TERMS", "\n, ,\n")
        settings = load_settings()
        assert settings.prompt.domain_terms == []

    def test_empty_custom_rules_ignored(self, monkeypatch):
        """PROMPT_CUSTOM_RULES with only whitespace should not override"""
        monkeypatch.setenv("PROMPT_CUSTOM_RULES", "\n\n")
        settings = load_settings()
        assert settings.prompt.custom_rules == []


class TestLoaderYamlEdgeCases:
    """Test _load_yaml_file and load_settings YAML edge cases"""

    def test_load_nonexistent_yaml_returns_none(self, tmp_path):
        """_load_yaml_file returns None when file doesn't exist"""
        from config.loader import _load_yaml_file
        assert _load_yaml_file(tmp_path / "missing.yaml") is None

    def test_load_invalid_yaml_returns_none(self, tmp_path, caplog):
        """_load_yaml_file returns None and logs warning on invalid YAML"""
        from config.loader import _load_yaml_file
        bad = tmp_path / "bad.yaml"
        bad.write_text("key: [unclosed")
        with caplog.at_level(logging.WARNING):
            result = _load_yaml_file(bad)
        assert result is None
        assert any("Failed to load config" in r.message for r in caplog.records)

    def test_load_empty_yaml_returns_empty_dict(self, tmp_path):
        """Empty YAML file results in empty dict (yaml.safe_load falsy)"""
        from config.loader import _load_yaml_file
        empty = tmp_path / "empty.yaml"
        empty.write_text("")
        assert _load_yaml_file(empty) == {}

    def test_load_settings_search_path_hit(self, tmp_path, caplog, monkeypatch):
        """load_settings() without explicit path loads from search path and logs info"""
        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()
        cfg_file = cfg_dir / "config.yaml"
        cfg_file.write_text("app:\n  name: search-path-app\n")
        monkeypatch.setenv("MANUAL_PROCESSOR_CONFIG", str(cfg_file))
        # Clear cached search paths so env var takes effect
        import config.loader as loader_mod
        original_paths = loader_mod.CONFIG_SEARCH_PATHS
        loader_mod.CONFIG_SEARCH_PATHS = [Path(str(cfg_file))]
        try:
            with caplog.at_level(logging.INFO):
                settings = load_settings()
            assert settings.app.name == "search-path-app"
            assert any("Loaded config from" in r.message for r in caplog.records)
        finally:
            loader_mod.CONFIG_SEARCH_PATHS = original_paths

    def test_load_settings_validation_error(self, monkeypatch, caplog):
        """load_settings() raises ValidationError on invalid config values"""
        monkeypatch.setenv("WEB_PORT", "99999")
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception):
                load_settings()
        assert any("Configuration validation failed" in r.message for r in caplog.records)

    def test_find_config_file_returns_existing(self, tmp_path, monkeypatch):
        """find_config_file() returns path when a search path exists"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("app:\n  name: x\n")
        import config.loader as loader_mod
        original_paths = loader_mod.CONFIG_SEARCH_PATHS
        loader_mod.CONFIG_SEARCH_PATHS = [Path(str(cfg_file))]
        try:
            result = find_config_file()
            assert result == cfg_file
        finally:
            loader_mod.CONFIG_SEARCH_PATHS = original_paths

    def test_find_config_file_returns_none(self, tmp_path, monkeypatch):
        """find_config_file() returns None when no search path exists"""
        import config.loader as loader_mod
        original_paths = loader_mod.CONFIG_SEARCH_PATHS
        loader_mod.CONFIG_SEARCH_PATHS = [tmp_path / "nope.yaml"]
        try:
            assert find_config_file() is None
        finally:
            loader_mod.CONFIG_SEARCH_PATHS = original_paths

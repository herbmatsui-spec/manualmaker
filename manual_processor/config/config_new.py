"""
Backward-compatible configuration wrapper.
Uses new Pydantic Settings internally while preserving existing API.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional, ClassVar

from config.settings import Settings
from config.loader import load_settings

logger = logging.getLogger(__name__)


class AppConfig:
    """
    Backward-compatible configuration class.
    
    Internally uses new Pydantic Settings while preserving
    the existing API (Config.get_instance(), from_env(), etc.)
    """
    _instance: ClassVar[Optional['AppConfig']] = None
    _settings: ClassVar[Optional[Settings]] = None

    def __init__(self, settings: Optional[Settings] = None, **kwargs):
        """
        Initialize AppConfig.
        
        Args:
            settings: Optional Pydantic Settings instance
            **kwargs: Legacy keyword arguments for backward compatibility
        """
        if settings:
            self._settings = settings
        else:
            # Handle legacy keyword arguments
            if kwargs:
                # Build settings from legacy kwargs
                settings_data = {}
                
                # Map legacy kwargs to new settings structure
                if 'google_cloud_project_id' in kwargs:
                    # Store in a way that doesn't conflict with new settings
                    pass
                
                # Create settings with overrides
                self._settings = load_settings()
                
                # Apply legacy overrides via environment for compatibility
                for key, value in kwargs.items():
                    env_key = key.upper()
                    if value is not None:
                        os.environ[env_key] = str(value)
                
                # Reload with env overrides
                self._settings = load_settings()
            else:
                self._settings = load_settings()

    @property
    def google_cloud_project_id(self) -> str:
        return os.getenv("GOOGLE_CLOUD_PROJECT_ID", "")

    @property
    def vision_api(self) -> bool:
        legacy_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        return os.getenv("VISION_API", "True").lower() in ("true", "1", "yes") or bool(legacy_key)

    @property
    def google_application_credentials(self) -> str:
        return os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    @property
    def vision_api_timeout(self) -> int:
        return self._settings.ocr.timeout_seconds

    @property
    def vision_max_results(self) -> int:
        return self._settings.ocr.max_results

    @property
    def gemini_model_name(self) -> str:
        return self._settings.gemini.model

    @property
    def gemini_temperature(self) -> float:
        return self._settings.gemini.temperature

    @property
    def gemini_max_output_tokens(self) -> int:
        return self._settings.gemini.max_output_tokens

    @property
    def chunk_size(self) -> int:
        return self._settings.processing.chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self._settings.processing.chunk_overlap

    @property
    def processor_type(self) -> str:
        return self._settings.processing.processor_type

    @property
    def fallback_enabled(self) -> bool:
        return self._settings.processing.fallback_enabled

    @property
    def web_host(self) -> str:
        return self._settings.web.host

    @property
    def web_port(self) -> int:
        return self._settings.web.port

    @property
    def web_cors_origins(self) -> List[str]:
        return self._settings.web.cors_origins

    @property
    def web_upload_max_mb(self) -> int:
        return self._settings.web.upload_max_mb

    @property
    def prompt_layout(self) -> str:
        return self._settings.prompt.layout

    @prompt_layout.setter
    def prompt_layout(self, value: str) -> None:
        self._settings.prompt.layout = value

    @property
    def prompt_domain_terms(self) -> List[str]:
        return self._settings.prompt.domain_terms

    @prompt_domain_terms.setter
    def prompt_domain_terms(self, value: List[str]) -> None:
        self._settings.prompt.domain_terms = value

    @property
    def prompt_has_diagrams(self) -> bool:
        return self._settings.prompt.has_diagrams

    @prompt_has_diagrams.setter
    def prompt_has_diagrams(self, value: bool) -> None:
        self._settings.prompt.has_diagrams = value

    @property
    def prompt_low_quality_mode(self) -> bool:
        return self._settings.prompt.low_quality_mode

    @prompt_low_quality_mode.setter
    def prompt_low_quality_mode(self, value: bool) -> None:
        self._settings.prompt.low_quality_mode = value

    @property
    def prompt_strict_mode(self) -> bool:
        return self._settings.prompt.strict_mode

    @prompt_strict_mode.setter
    def prompt_strict_mode(self, value: bool) -> None:
        self._settings.prompt.strict_mode = value

    @property
    def prompt_custom_rules(self) -> List[str]:
        return self._settings.prompt.custom_rules

    @prompt_custom_rules.setter
    def prompt_custom_rules(self, value: List[str]) -> None:
        self._settings.prompt.custom_rules = value

    @property
    def generate_diagram(self) -> bool:
        return self._settings.prompt.generate_diagram

    @property
    def generate_diagram_png(self) -> bool:
        return self._settings.prompt.generate_diagram_png

    @property
    def generate_diagram_markdown(self) -> bool:
        return self._settings.prompt.generate_diagram_markdown

    @property
    def generate_diagram_mermaid(self) -> bool:
        return self._settings.prompt.generate_diagram_mermaid

    @property
    def tts_language_code(self) -> str:
        return self._settings.tts.language_code

    @property
    def tts_voice_name(self) -> str:
        return self._settings.tts.voice_name

    @property
    def tts_speaking_rate(self) -> float:
        return self._settings.tts.speaking_rate

    @property
    def tts_pitch(self) -> float:
        return self._settings.tts.pitch

    @property
    def usb_monitor_paths(self) -> List[str]:
        return self._settings.usb.paths

    @property
    def usb_auto_detect(self) -> bool:
        return self._settings.usb.auto_detect

    @property
    def usb_poll_interval(self) -> float:
        return self._settings.usb.poll_interval

    @property
    def default_language(self) -> str:
        return os.getenv("APP_LANGUAGE", "ja").lower()

    @property
    def output_directory(self) -> Path:
        return Path(self._settings.paths.output_directory)

    @property
    def temp_directory(self) -> Path:
        return Path(self._settings.paths.temp_directory)

    @property
    def pdf_dpi(self) -> int:
        return int(os.getenv("PDF_DPI", "300"))

    @property
    def max_file_size_mb(self) -> int:
        return int(os.getenv("MAX_FILE_SIZE_MB", "50"))

    @property
    def supported_extensions(self) -> List[str]:
        exts = os.getenv("SUPPORTED_EXTENSIONS", ".pdf")
        return [ext.strip() for ext in exts.split(",") if ext.strip()] or [".pdf"]

    @property
    def pii_masking_enabled(self) -> bool:
        return self._settings.security.pii_masking.enabled

    # Backward compatibility properties
    @property
    def google_api_key(self) -> str:
        return ""

    @property
    def gemini_api_key(self) -> str:
        return ""

    @property
    def ocr_model(self) -> str:
        return "gemini-1.5-flash" if not self.vision_api else "vision-api"

    @property
    def summary_model(self) -> str:
        return self.gemini_model_name

    @property
    def tts_model(self) -> str:
        return "gemini-2.5-flash-tts"

    @property
    def tts_fallback_model(self) -> str:
        return "gemini-3.1-flash-tts"

    @property
    def compact_layout(self) -> bool:
        return False

    @property
    def use_emojis(self) -> bool:
        return False

    @property
    def diagram_theme(self) -> str:
        return "default"

    @property
    def diagram_width(self) -> int:
        return 800

    @property
    def diagram_height(self) -> int:
        return 600

    @classmethod
    def get_instance(cls) -> 'AppConfig':
        """シングルトンインスタンスを取得"""
        if cls._instance is None:
            cls._instance = cls.from_env()
        return cls._instance

    @classmethod
    def from_env(cls) -> 'AppConfig':
        """環境変数から設定を読み込み"""
        settings = load_settings()
        return cls(settings=settings)

    def validate(self) -> List[str]:
        """設定の妥当性を検証し、エラーのリストを返す"""
        errors = []

        if not self.google_cloud_project_id or not self.google_cloud_project_id.strip():
            errors.append("GOOGLE_CLOUD_PROJECT_ID is not set")

        if self.vision_api:
            has_service_account = bool(self.google_application_credentials and self.google_application_credentials.strip())
            has_legacy_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
            if not (has_service_account or has_legacy_key):
                errors.append("Either GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_API_KEY/GEMINI_API_KEY is required")

        if self.vision_api_timeout <= 0:
            errors.append("VISION_API_TIMEOUT must be positive")

        if self.vision_max_results <= 0:
            errors.append("VISION_MAX_RESULTS must be positive")

        if not (0.0 <= self.gemini_temperature <= 1.0):
            errors.append("GEMINI_TEMPERATURE must be between 0.0 and 1.0")

        if self.gemini_max_output_tokens <= 0:
            errors.append("GEMINI_MAX_OUTPUT_TOKENS must be positive")

        if self.tts_speaking_rate <= 0:
            errors.append("TTS_SPEAKING_RATE must be positive")

        if not self.output_directory:
            errors.append("OUTPUT_DIRECTORY is not set")

        if not self.temp_directory:
            errors.append("TEMP_DIRECTORY is not set")

        if self.pdf_dpi <= 0:
            errors.append("PDF_DPI must be positive")
        elif self.pdf_dpi > 600:
            errors.append("PDF_DPI exceeds 600 (may cause memory issues)")

        if self.max_file_size_mb <= 0:
            errors.append("MAX_FILE_SIZE_MB must be positive")

        if not self.supported_extensions:
            errors.append("SUPPORTED_EXTENSIONS is not set")

        return errors

    def ensure_directories(self) -> None:
        """出力ディレクトリとテンポラリディレクトリを作成"""
        for dir_path, label in [(self.output_directory, "output"), (self.temp_directory, "temp")]:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                raise ValueError(f"Permission denied for {label} directory: {dir_path}")
            except OSError as e:
                raise ValueError(f"Failed to create {label} directory: {dir_path} ({e})")


# Alias for backward compatibility
Config = AppConfig

"""
Configuration loader that merges YAML and environment variables.
Priority: defaults < YAML < environment variables
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import ValidationError

from config.settings import Settings

logger = logging.getLogger(__name__)

# Search paths for config file
CONFIG_SEARCH_PATHS = [
    Path(os.getenv("MANUAL_PROCESSOR_CONFIG", "")),
    Path("./config.yaml"),
    Path("./config/config.yaml"),
    Path.home() / ".config" / "manual-processor" / "config.yaml",
]


def find_config_file() -> Optional[Path]:
    """
    Find configuration file in search paths.
    
    Returns:
        Path to config file if found, None otherwise
    """
    for path in CONFIG_SEARCH_PATHS:
        if path and path.exists() and path.is_file():
            return path
    return None


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.
    
    Args:
        base: Base dictionary
        override: Override dictionary (takes precedence)
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml_file(path: Path) -> Optional[Dict[str, Any]]:
    """
    Load YAML configuration file.
    
    Args:
        path: Path to YAML file
        
    Returns:
        Dictionary with config, or None if file doesn't exist
    """
    if not path.exists():
        return None

    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load config from {path}: {e}")
        return None


def _env_to_settings_mapping() -> Dict[str, Any]:
    """
    Map environment variables to settings structure.
    
    Returns:
        Dictionary with environment variable overrides
    """
    overrides: Dict[str, Any] = {}

    # App settings
    if "APP_DEBUG" in os.environ:
        overrides.setdefault("app", {})["debug"] = os.getenv("APP_DEBUG").lower() in ("true", "1", "yes")

    # Path settings
    if "OUTPUT_DIRECTORY" in os.environ:
        overrides.setdefault("paths", {})["output_directory"] = os.getenv("OUTPUT_DIRECTORY")
    if "TEMP_DIRECTORY" in os.environ:
        overrides.setdefault("paths", {})["temp_directory"] = os.getenv("TEMP_DIRECTORY")
    if "LOG_DIRECTORY" in os.environ:
        overrides.setdefault("paths", {})["log_directory"] = os.getenv("LOG_DIRECTORY")

    # OCR settings
    if "OCR_PROVIDER" in os.environ:
        overrides.setdefault("ocr", {})["provider"] = os.getenv("OCR_PROVIDER")
    if "OCR_BATCH_SIZE" in os.environ:
        overrides.setdefault("ocr", {})["batch_size"] = int(os.getenv("OCR_BATCH_SIZE"))
    if "OCR_TIMEOUT" in os.environ:
        overrides.setdefault("ocr", {})["timeout_seconds"] = int(os.getenv("OCR_TIMEOUT"))

    # Gemini settings
    if "GEMINI_MODEL" in os.environ:
        overrides.setdefault("gemini", {})["model"] = os.getenv("GEMINI_MODEL")
    if "GEMINI_TEMPERATURE" in os.environ:
        overrides.setdefault("gemini", {})["temperature"] = float(os.getenv("GEMINI_TEMPERATURE"))
    if "GEMINI_MAX_TOKENS" in os.environ:
        overrides.setdefault("gemini", {})["max_output_tokens"] = int(os.getenv("GEMINI_MAX_TOKENS"))

    # Processing settings
    if "PROCESSOR_TYPE" in os.environ:
        overrides.setdefault("processing", {})["processor_type"] = os.getenv("PROCESSOR_TYPE")
    if "CHUNK_SIZE" in os.environ:
        overrides.setdefault("processing", {})["chunk_size"] = int(os.getenv("CHUNK_SIZE"))

    # Web settings
    if "WEB_HOST" in os.environ:
        overrides.setdefault("web", {})["host"] = os.getenv("WEB_HOST")
    if "WEB_PORT" in os.environ:
        overrides.setdefault("web", {})["port"] = int(os.getenv("WEB_PORT"))
    if "WEB_CORS_ORIGINS" in os.environ:
        origins = [o.strip() for o in os.getenv("WEB_CORS_ORIGINS", "").split(",") if o.strip()]
        if origins:
            overrides.setdefault("web", {})["cors_origins"] = origins
    if "WEB_UPLOAD_MAX_MB" in os.environ:
        overrides.setdefault("web", {})["upload_max_mb"] = int(os.getenv("WEB_UPLOAD_MAX_MB"))

    # Prompt settings
    if "PROMPT_LAYOUT" in os.environ:
        overrides.setdefault("prompt", {})["layout"] = os.getenv("PROMPT_LAYOUT")
    if "PROMPT_STRICT_MODE" in os.environ:
        overrides.setdefault("prompt", {})["strict_mode"] = os.getenv("PROMPT_STRICT_MODE").lower() in ("true", "1", "yes")

    # TTS settings
    if "TTS_LANGUAGE" in os.environ:
        overrides.setdefault("tts", {})["language_code"] = os.getenv("TTS_LANGUAGE")
    if "TTS_VOICE" in os.environ:
        overrides.setdefault("tts", {})["voice_name"] = os.getenv("TTS_VOICE")

    # Security settings
    if "PII_MASKING_ENABLED" in os.environ:
        overrides.setdefault("security", {}).setdefault("pii_masking", {})["enabled"] = os.getenv("PII_MASKING_ENABLED").lower() in ("true", "1", "yes")
    if "AUDIT_ENABLED" in os.environ:
        overrides.setdefault("security", {}).setdefault("audit", {})["enabled"] = os.getenv("AUDIT_ENABLED").lower() in ("true", "1", "yes")

    # USB settings
    if "USB_AUTO_DETECT" in os.environ:
        overrides.setdefault("usb", {})["auto_detect"] = os.getenv("USB_AUTO_DETECT").lower() in ("true", "1", "yes")

    return overrides


def load_settings(config_path: Optional[Path] = None) -> Settings:
    """
    Load settings from YAML file and environment variables.
    
    Priority (highest to lowest):
    1. Environment variables
    2. YAML config file
    3. Default values
    
    Args:
        config_path: Optional explicit path to config file
        
    Returns:
        Settings instance
    """
    # Start with defaults
    config_data: Dict[str, Any] = {}

    # Load YAML config
    yaml_config = None
    if config_path:
        yaml_config = _load_yaml_file(config_path)
    else:
        for path in CONFIG_SEARCH_PATHS:
            if path and path.exists():
                yaml_config = _load_yaml_file(path)
                if yaml_config:
                    logger.info(f"Loaded config from {path}")
                    break

    if yaml_config:
        config_data = _deep_merge(config_data, yaml_config)

    # Apply environment variable overrides
    env_overrides = _env_to_settings_mapping()
    if env_overrides:
        config_data = _deep_merge(config_data, env_overrides)
        logger.debug(f"Applied {len(env_overrides)} environment overrides")

    # Create Settings instance
    try:
        return Settings(**config_data)
    except ValidationError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise

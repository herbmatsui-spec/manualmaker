"""
Configuration validation command-line tool.
Validates YAML config files and environment variables.
"""

import sys
import logging
from pathlib import Path
from typing import List

from config.loader import load_settings
from config.settings import Settings

logger = logging.getLogger(__name__)


def validate_config_file(config_path: Path) -> int:
    """
    Validate a configuration file.
    
    Args:
        config_path: Path to YAML config file
        
    Returns:
        Exit code (0=success, 1=error)
    """
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        return 1

    try:
        settings = load_settings(config_path)
        print(f"✓ Config file is valid: {config_path}")
        print(f"  App: {settings.app.name} v{settings.app.version}")
        print(f"  Web: {settings.web.host}:{settings.web.port}")
        print(f"  OCR: {settings.ocr.provider}")
        print(f"  Gemini: {settings.gemini.model}")
        return 0
    except Exception as e:
        print(f"ERROR: Config validation failed: {e}")
        logger.error(f"Config validation failed: {e}", exc_info=True)
        return 1


def validate_current_config() -> int:
    """
    Validate current configuration (from env/defaults).
    
    Returns:
        Exit code (0=success, 1=error)
    """
    try:
        settings = load_settings()
        print(f"✓ Current config is valid")
        print(f"  App: {settings.app.name} v{settings.app.version}")
        print(f"  Debug: {settings.app.debug}")
        return 0
    except Exception as e:
        print(f"ERROR: Current config validation failed: {e}")
        return 1


def main(args: List[str] = None) -> int:
    """
    Main entry point for config validation.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    if args is None:
        args = sys.argv[1:]

    if not args:
        return validate_current_config()

    config_path = Path(args[0])
    return validate_config_file(config_path)


if __name__ == "__main__":
    sys.exit(main())

"""
Configuration module - backward compatibility wrapper.
This module re-exports from config_new for backward compatibility.
"""

from config.config_new import AppConfig, Config

__all__ = ["AppConfig", "Config"]

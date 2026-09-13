"""
Configuration module for Manual Processor.
Supports both local development and Cloudflare Pages Functions / Workers.
"""

import os
from config.cloudflare_config import Config, CloudflareConfig, CloudflareBindings, init_cloudflare_config

# For backward compatibility
AppConfig = Config

# Auto-initialize with Cloudflare bindings if available
# This allows Pages Functions to pass bindings at runtime
def _try_init_from_env():
    """Try to initialize from environment (for local dev)"""
    # Check if we're in a Cloudflare environment
    if os.getenv("ENVIRONMENT") in ("production", "preview"):
        # Bindings will be injected by Pages Functions runtime
        pass

_try_init_from_env()

__all__ = ["Config", "AppConfig", "CloudflareConfig", "CloudflareBindings", "init_cloudflare_config"]
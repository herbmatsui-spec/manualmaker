"""
Keyring-based secure storage for API keys.
Provides encrypted storage of sensitive API keys using system keyring.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import keyring
    _HAS_KEYRING = True
except ImportError:
    _HAS_KEYRING = False

SERVICE_NAME = "manual_processor"


def get_api_key(service: str, username: str) -> Optional[str]:
    """
    Get API key from system keyring.

    Args:
        service: Service name (e.g., "gemini", "google_cloud_vision")
        username: Username/ID for the key (e.g., "api_key", "oauth_token")

    Returns:
        API key string if found, None otherwise
    """
    if _HAS_KEYRING:
        try:
            key = keyring.get_password(service, username)
            if key:
                logger.debug(f"Retrieved API key for {service}/{username} from keyring")
            else:
                logger.warning(f"No API key found for {service}/{username} in keyring")
            return key
        except Exception as e:
            logger.error(f"Failed to retrieve API key from keyring: {e}")
            return None
    else:
        logger.warning("keyring not available, falling back to environment variable")
        return _get_from_env(service, username)


def set_api_key(service: str, username: str, value: str) -> None:
    """
    Store API key in system keyring.

    Args:
        service: Service name
        username: Username/ID
        value: API key value to store
    """
    if not value:
        raise ValueError("API key value cannot be empty")
    
    if _HAS_KEYRING:
        try:
            keyring.set_password(service, username, value)
            logger.info(f"Stored API key for {service}/{username} in keyring")
        except Exception as e:
            logger.error(f"Failed to store API key in keyring: {e}")
            raise
    else:
        _set_env(service, username, value)


def delete_api_key(service: str, username: str) -> None:
    """
    Delete API key from system keyring.

    Args:
        service: Service name
        username: Username/ID
    """
    if _HAS_KEYRING:
        try:
            keyring.delete_password(service, username)
            logger.info(f"Deleted API key for {service}/{username} from keyring")
        except Exception as e:
            logger.error(f"Failed to delete API key from keyring: {e}")
            raise
    else:
        _delete_env(service, username)


def key_exists(service: str, username: str) -> bool:
    """
    Check if API key exists in keyring.

    Args:
        service: Service name
        username: Username/ID

    Returns:
        True if key exists, False otherwise
    """
    if _HAS_KEYRING:
        return keyring.get_password(service, username) is not None
    else:
        return _env_exists(service, username)

# Environment variable fallback functions
_ENV_PREFIX = "MANUAL_PROCESSOR_"


def _get_from_env(service: str, username: str) -> Optional[str]:
    """Fallback to environment variable storage."""
    env_var = f"{_ENV_PREFIX}{service.upper()}_{username.upper()}"
    return os.environ.get(env_var)


def _set_env(service: str, username: str, value: str) -> None:
    """Store in environment variable (only for fallback)."""
    env_var = f"{_ENV_PREFIX}{service.upper()}_{username.upper()}"
    os.environ[env_var] = value


def _delete_env(service: str, username: str) -> None:
    """Delete from environment variable (only for fallback)."""
    env_var = f"{_ENV_PREFIX}{service.upper()}_{username.upper()}"
    os.environ.pop(env_var, None)


def _env_exists(service: str, username: str) -> bool:
    """Check environment variable."""
    env_var = f"{_ENV_PREFIX}{service.upper()}_{username.upper()}"
    return env_var in os.environ


def log_api_key_usage(service: str, username: str, action: str) -> None:
    """
    Log API key usage (with key value redacted).

    Args:
        service: Service name
        username: Username/ID
        action: Action performed
    """
    if not key_exists(service, username):
        logger.warning(f"API key access for {service}/{username} when key not present")
    
    logger.info(
        f"API key {action}: {service}/{username} "
        f"(key: {'[REDACTED]' if key_exists(service, username) else 'NOT FOUND'})"
    )

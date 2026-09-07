"""
Tests for keyring_store module.
Tests secure API key storage using system keyring with environment variable fallback.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from src.security.keyring_store import (
    get_api_key,
    set_api_key,
    delete_api_key,
    key_exists,
    log_api_key_usage,
    _get_from_env,
    _set_env,
    _delete_env,
    _env_exists,
    _HAS_KEYRING,
    _ENV_PREFIX,
)


class TestSetApiKey:
    """Tests for set_api_key function"""

    def test_set_api_key_success(self):
        """Test successfully storing API key in keyring"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            set_api_key("gemini", "api_key", "secret123")
            mock_keyring.set_password.assert_called_once_with("gemini", "api_key", "secret123")

    def test_set_api_key_failure_permission_error(self):
        """Test set_api_key raises PermissionError when keyring fails"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            mock_keyring.set_password.side_effect = PermissionError("Access denied")
            with pytest.raises(PermissionError):
                set_api_key("gemini", "api_key", "secret123")

    def test_set_api_key_empty_value_raises(self):
        """Test that empty API key value raises ValueError"""
        with pytest.raises(ValueError, match="API key value cannot be empty"):
            set_api_key("gemini", "api_key", "")

    def test_set_api_key_no_keyring_fallback(self):
        """Test set_api_key falls back to env var when keyring unavailable"""
        with patch('src.security.keyring_store.keyring', None):
            with patch('src.security.keyring_store._HAS_KEYRING', False):
                set_api_key("gemini", "api_key", "secret123")
                env_var = f"{_ENV_PREFIX}GEMINI_API_KEY"
                assert os.environ.get(env_var) == "secret123"


class TestGetApiKey:
    """Tests for get_api_key function"""

    def test_get_api_key_hit(self):
        """Test retrieving existing API key from keyring"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            mock_keyring.get_password.return_value = "secret123"
            result = get_api_key("gemini", "api_key")
            assert result == "secret123"
            mock_keyring.get_password.assert_called_once_with("gemini", "api_key")

    def test_get_api_key_miss(self):
        """Test retrieving non-existent API key returns None"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            mock_keyring.get_password.return_value = None
            result = get_api_key("gemini", "api_key")
            assert result is None

    def test_get_api_key_exception(self):
        """Test get_api_key returns None when keyring throws exception"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            mock_keyring.get_password.side_effect = Exception("Keyring error")
            result = get_api_key("gemini", "api_key")
            assert result is None

    def test_get_api_key_no_keyring_fallback(self):
        """Test get_api_key falls back to env var when keyring unavailable"""
        env_var = f"{_ENV_PREFIX}GEMINI_API_KEY"
        os.environ[env_var] = "fallback_secret"
        try:
            with patch('src.security.keyring_store.keyring', None):
                with patch('src.security.keyring_store._HAS_KEYRING', False):
                    result = get_api_key("gemini", "api_key")
                    assert result == "fallback_secret"
        finally:
            del os.environ[env_var]


class TestDeleteApiKey:
    """Tests for delete_api_key function"""

    def test_delete_api_key_success(self):
        """Test successfully deleting API key from keyring"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            delete_api_key("gemini", "api_key")
            mock_keyring.delete_password.assert_called_once_with("gemini", "api_key")

    def test_delete_api_key_failure(self):
        """Test delete_api_key raises when keyring fails"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            mock_keyring.delete_password.side_effect = Exception("Delete failed")
            with pytest.raises(Exception):
                delete_api_key("gemini", "api_key")

    def test_delete_api_key_already_deleted(self):
        """Test delete_api_key raises when key doesn't exist"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            mock_keyring.delete_password.side_effect = Exception("not found")
            with pytest.raises(Exception):
                delete_api_key("gemini", "api_key")

    def test_delete_api_key_no_keyring_fallback(self):
        """Test delete_api_key falls back to env var when keyring unavailable"""
        env_var = f"{_ENV_PREFIX}GEMINI_API_KEY"
        os.environ[env_var] = "secret"
        try:
            with patch('src.security.keyring_store.keyring', None):
                with patch('src.security.keyring_store._HAS_KEYRING', False):
                    delete_api_key("gemini", "api_key")
                    assert env_var not in os.environ
        finally:
            if env_var in os.environ:
                del os.environ[env_var]


class TestKeyExists:
    """Tests for key_exists function"""

    def test_key_exists_true(self):
        """Test key_exists returns True when key is present"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            mock_keyring.get_password.return_value = "some_value"
            assert key_exists("gemini", "api_key") is True

    def test_key_exists_false(self):
        """Test key_exists returns False when key is absent"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            mock_keyring.get_password.return_value = None
            assert key_exists("gemini", "api_key") is False

    def test_key_exists_no_keyring_fallback(self):
        """Test key_exists checks env var when keyring unavailable"""
        env_var = f"{_ENV_PREFIX}GEMINI_API_KEY"
        os.environ[env_var] = "secret"
        try:
            with patch('src.security.keyring_store.keyring', None):
                with patch('src.security.keyring_store._HAS_KEYRING', False):
                    assert key_exists("gemini", "api_key") is True
        finally:
            del os.environ[env_var]


class TestEnvFallback:
    """Tests for environment variable fallback functions"""

    def test_get_from_env(self):
        """Test _get_from_env retrieves from environment"""
        env_var = f"{_ENV_PREFIX}TEST_SERVICE_KEY"
        os.environ[env_var] = "test_value"
        try:
            result = _get_from_env("test_service", "key")
            assert result == "test_value"
        finally:
            del os.environ[env_var]

    def test_get_from_env_not_found(self):
        """Test _get_from_env returns None when env var not set"""
        result = _get_from_env("nonexistent", "service")
        assert result is None

    def test_set_env(self):
        """Test _set_env stores in environment variable"""
        env_var = f"{_ENV_PREFIX}TEST_SERVICE_KEY"
        _set_env("test_service", "key", "test_value")
        try:
            assert os.environ[env_var] == "test_value"
        finally:
            del os.environ[env_var]

    def test_delete_env(self):
        """Test _delete_env removes from environment"""
        env_var = f"{_ENV_PREFIX}TEST_SERVICE_KEY"
        os.environ[env_var] = "test_value"
        _delete_env("test_service", "key")
        assert env_var not in os.environ

    def test_delete_env_not_exists(self):
        """Test _delete_env doesn't raise when env var doesn't exist"""
        _delete_env("nonexistent", "service")

    def test_env_exists_true(self):
        """Test _env_exists returns True when env var exists"""
        env_var = f"{_ENV_PREFIX}TEST_SERVICE_KEY"
        os.environ[env_var] = "test_value"
        try:
            assert _env_exists("test_service", "key") is True
        finally:
            del os.environ[env_var]

    def test_env_exists_false(self):
        """Test _env_exists returns False when env var doesn't exist"""
        assert _env_exists("nonexistent", "service") is False


class TestLogApiKeyUsage:
    """Tests for log_api_key_usage function"""

    def test_log_api_key_usage_key_present(self, caplog):
        """Test log_api_key_usage logs correctly when key exists"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            mock_keyring.get_password.return_value = "secret"
            import logging
            caplog.set_level(logging.INFO)
            log_api_key_usage("gemini", "api_key", "retrieved")
            assert any("retrieved" in record.message for record in caplog.records)

    def test_log_api_key_usage_key_absent(self, caplog):
        """Test log_api_key_usage logs warning when key doesn't exist"""
        with patch('src.security.keyring_store.keyring') as mock_keyring:
            mock_keyring.get_password.return_value = None
            import logging
            caplog.set_level(logging.WARNING)
            log_api_key_usage("gemini", "api_key", "retrieved")
            assert any("when key not present" in record.message for record in caplog.records)

"""Tests for src/security_manager.py"""

import json
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestSecurityManagerMasking:
    """Tests for SecurityManager masking functions"""

    def setup_method(self):
        from src.security_manager import SecurityManager
        SecurityManager.PATTERNS = []

    def test_mask_sensitive_data_empty(self):
        from src.security_manager import SecurityManager

        masked, info = SecurityManager.mask_sensitive_data("")
        assert masked == ""
        assert info == {"counts": {}}

    def test_mask_sensitive_data_no_pii(self):
        from src.security_manager import SecurityManager

        masked, info = SecurityManager.mask_sensitive_data("Hello world")
        assert masked == "Hello world"
        assert info["counts"] == {}

    def test_mask_email(self):
        from src.security_manager import SecurityManager

        masked, info = SecurityManager.mask_sensitive_data("Contact: test@example.com")
        assert "[REDACTED_EMAIL]" in masked
        assert info["counts"]["EMAIL"] == 1

    def test_mask_phone(self):
        from src.security_manager import SecurityManager

        masked, info = SecurityManager.mask_sensitive_data("電話: 03-1234-5678")
        assert "[REDACTED_PHONE]" in masked
        assert "PHONE_JP" in info["counts"]

    def test_mask_multiple_pii_types(self):
        from src.security_manager import SecurityManager

        masked, info = SecurityManager.mask_sensitive_data(
            "Email: user@test.com, Phone: 03-1234-5678"
        )
        assert "[REDACTED_EMAIL]" in masked
        assert "[REDACTED_PHONE]" in masked
        assert info["counts"]["EMAIL"] == 1
        assert info["counts"]["PHONE_JP"] == 1

    def test_mask_sensitive_data_with_positions(self):
        from src.security_manager import SecurityManager

        masked, info = SecurityManager.mask_sensitive_data(
            "Email: test@example.com",
            record_positions=True
        )
        assert "[REDACTED_EMAIL]" in masked
        assert "positions" in info
        assert len(info["positions"]) == 1
        assert info["positions"][0].mask_type == "EMAIL"

    def test_unmask_data(self):
        from src.security_manager import SecurityManager, MaskedPosition

        masked = "Email: [REDACTED_EMAIL], Phone: [REDACTED_PHONE]"
        positions = [
            MaskedPosition(start=7, end=22, mask_type="EMAIL", original_length=16),
            MaskedPosition(start=30, end=45, mask_type="PHONE", original_length=14)
        ]
        originals = ["test@example.com", "03-1234-5678"]

        result = SecurityManager.unmask_data(masked, positions, originals)
        assert "test@example.com" in result
        assert "03-1234-5678" in result

    def test_unmask_data_empty(self):
        from src.security_manager import SecurityManager

        result = SecurityManager.unmask_data("test", [], [])
        assert result == "test"

    def test_unmask_data_mismatched_lengths(self):
        from src.security_manager import SecurityManager, MaskedPosition

        result = SecurityManager.unmask_data("[REDACTED]", [], ["value"])
        assert result == "[REDACTED]"


class TestSecurityManagerAPIKey:
    """Tests for API key storage"""

    def test_save_api_key_no_keyring(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_KEYRING', False):
            result = SecurityManager.save_api_key("test-key")
            assert result is False

    def test_save_api_key_success(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_KEYRING', True):
            with patch('src.security_manager.keyring.set_password') as mock_set:
                result = SecurityManager.save_api_key("test-key")
                assert result is True
                mock_set.assert_called_once()

    def test_save_api_key_error(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_KEYRING', True):
            with patch('src.security_manager.keyring.set_password', side_effect=Exception("Error")):
                result = SecurityManager.save_api_key("test-key")
                assert result is False

    def test_load_api_key_no_keyring(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_KEYRING', False):
            result = SecurityManager.load_api_key()
            assert result is None

    def test_load_api_key_success(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_KEYRING', True):
            with patch('src.security_manager.keyring.get_password', return_value="test-key"):
                result = SecurityManager.load_api_key()
                assert result == "test-key"

    def test_load_api_key_error(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_KEYRING', True):
            with patch('src.security_manager.keyring.get_password', side_effect=Exception("Error")):
                result = SecurityManager.load_api_key()
                assert result is None


class TestSecurityManagerEncryption:
    """Tests for encryption functions"""

    def test_encrypt_no_crypto(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_CRYPTO', False):
            data = b"secret"
            encrypted, success = SecurityManager.encrypt_data(data)
            assert encrypted == data
            assert success is False

    def test_encrypt_no_key(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_CRYPTO', True):
            with patch.dict('os.environ', {}, clear=True):
                data = b"secret"
                encrypted, success = SecurityManager.encrypt_data(data)
                assert encrypted == data
                assert success is False

    def test_encrypt_success(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_CRYPTO', True):
            with patch.dict('os.environ', {'ENCRYPTION_KEY': 'test-encryption-key-32bytes!!!'}):
                with patch('src.security_manager.Fernet') as mock_fernet:
                    mock_fernet_instance = MagicMock()
                    mock_fernet.return_value = mock_fernet_instance
                    mock_fernet_instance.encrypt.return_value = b"encrypted_data"

                    data = b"secret"
                    encrypted, success = SecurityManager.encrypt_data(data)
                    assert success is True

    def test_encrypt_error(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_CRYPTO', True):
            with patch.dict('os.environ', {'ENCRYPTION_KEY': 'test-encryption-key-32bytes!!!'}):
                with patch('src.security_manager.Fernet', side_effect=Exception("Crypto error")):
                    data = b"secret"
                    encrypted, success = SecurityManager.encrypt_data(data)
                    assert success is False

    def test_decrypt_no_crypto(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_CRYPTO', False):
            data = b"encrypted"
            decrypted, success = SecurityManager.decrypt_data(data)
            assert decrypted == data
            assert success is False

    def test_decrypt_no_key(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_CRYPTO', True):
            with patch.dict('os.environ', {}, clear=True):
                data = b"encrypted"
                decrypted, success = SecurityManager.decrypt_data(data)
                assert decrypted == data
                assert success is False

    def test_decrypt_success(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_CRYPTO', True):
            with patch.dict('os.environ', {'ENCRYPTION_KEY': 'test-encryption-key-32bytes!!!'}):
                with patch('src.security_manager.Fernet') as mock_fernet:
                    mock_fernet_instance = MagicMock()
                    mock_fernet.return_value = mock_fernet_instance
                    mock_fernet_instance.decrypt.return_value = b"decrypted_data"

                    data = b"encrypted"
                    decrypted, success = SecurityManager.decrypt_data(data)
                    assert success is True

    def test_decrypt_error(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_CRYPTO', True):
            with patch.dict('os.environ', {'ENCRYPTION_KEY': 'test-encryption-key-32bytes!!!'}):
                with patch('src.security_manager.Fernet', side_effect=Exception("Crypto error")):
                    data = b"encrypted"
                    decrypted, success = SecurityManager.decrypt_data(data)
                    assert success is False


class TestSecurityManagerSecureDelete:
    """Tests for secure delete"""

    def test_secure_delete_nonexistent(self):
        from src.security_manager import SecurityManager

        result = SecurityManager.secure_delete(Path("/nonexistent/file.txt"))
        assert result is False

    def test_secure_delete_success(self, tmp_path):
        from src.security_manager import SecurityManager

        test_file = tmp_path / "test.txt"
        test_file.write_text("secret data")

        result = SecurityManager.secure_delete(test_file)
        assert result is True
        assert not test_file.exists()

    def test_secure_delete_error(self, tmp_path):
        from src.security_manager import SecurityManager

        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        with patch('src.security_manager.os.urandom', side_effect=Exception("Random error")):
            result = SecurityManager.secure_delete(test_file)
            assert result is False


class TestLoadPIIPatterns:
    """Tests for PII pattern loading"""

    def setup_method(self):
        from src.security_manager import SecurityManager
        SecurityManager.PATTERNS = []

    def test_load_pii_patterns_cached(self):
        from src.security_manager import SecurityManager

        SecurityManager.PATTERNS = [("TEST", r"pattern", "[REDACTED]")]
        patterns = SecurityManager._load_pii_patterns()
        assert len(patterns) == 1
        assert patterns[0][0] == "TEST"

    def test_load_pii_patterns_yaml_not_found(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager.Path.exists', return_value=False):
            patterns = SecurityManager._load_pii_patterns()
            assert len(patterns) > 0

    def test_load_pii_patterns_no_yaml(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_YAML', False):
            with patch('src.security_manager.Path.exists', return_value=True):
                patterns = SecurityManager._load_pii_patterns()
                assert len(patterns) > 0

    def test_load_pii_patterns_yaml_error(self):
        from src.security_manager import SecurityManager

        with patch('src.security_manager._HAS_YAML', True):
            with patch('src.security_manager.Path.exists', return_value=True):
                with patch('builtins.open', side_effect=Exception("Read error")):
                    patterns = SecurityManager._load_pii_patterns()
                    assert len(patterns) > 0


class TestAuditLogger:
    """Tests for AuditLogger"""

    def setup_method(self):
        from src.security_manager import AuditLogger
        AuditLogger._instance = None
        AuditLogger._initialized = False

    def test_singleton(self):
        from src.security_manager import AuditLogger

        logger1 = AuditLogger()
        logger2 = AuditLogger()
        assert logger1 is logger2

    def test_log_creates_file(self, tmp_path):
        from src.security_manager import AuditLogger

        log_file = tmp_path / "audit.log"
        with patch.object(AuditLogger, '_audit_file', log_file):
            logger = AuditLogger.__new__(AuditLogger)
            logger._initialized = False
            logger._log_dir = tmp_path

            logger.log("user1", "READ", "document.pdf")

            assert log_file.exists()

    def test_log_writes_json(self, tmp_path):
        from src.security_manager import AuditLogger

        log_file = tmp_path / "audit.log"
        with patch.object(AuditLogger, '_audit_file', log_file):
            logger = AuditLogger.__new__(AuditLogger)
            logger._initialized = False
            logger._log_dir = tmp_path

            logger.log("user1", "READ", "doc.pdf", "detail info")

            content = log_file.read_text()
            entry = json.loads(content.strip())
            assert entry["user_id"] == "user1"
            assert entry["action"] == "READ"
            assert entry["resource"] == "doc.pdf"
            assert entry["details"] == "detail info"

    def test_log_access(self, tmp_path):
        from src.security_manager import AuditLogger

        log_file = tmp_path / "audit.log"
        with patch.object(AuditLogger, '_audit_file', log_file):
            logger = AuditLogger.__new__(AuditLogger)
            logger._initialized = False
            logger._log_dir = tmp_path

            logger.log_access("user1", "resource.pdf")

            content = log_file.read_text()
            entry = json.loads(content.strip())
            assert entry["action"] == "ACCESS"

    def test_log_modification(self, tmp_path):
        from src.security_manager import AuditLogger

        log_file = tmp_path / "audit.log"
        with patch.object(AuditLogger, '_audit_file', log_file):
            logger = AuditLogger.__new__(AuditLogger)
            logger._initialized = False
            logger._log_dir = tmp_path

            logger.log_modification("user1", "doc.pdf", "updated content")

            content = log_file.read_text()
            entry = json.loads(content.strip())
            assert entry["action"] == "MODIFY"

    def test_log_deletion(self, tmp_path):
        from src.security_manager import AuditLogger

        log_file = tmp_path / "audit.log"
        with patch.object(AuditLogger, '_audit_file', log_file):
            logger = AuditLogger.__new__(AuditLogger)
            logger._initialized = False
            logger._log_dir = tmp_path

            logger.log_deletion("user1", "doc.pdf")

            content = log_file.read_text()
            entry = json.loads(content.strip())
            assert entry["action"] == "DELETE"

    def test_get_recent_logs_empty(self, tmp_path):
        from src.security_manager import AuditLogger

        log_file = tmp_path / "audit.log"
        with patch.object(AuditLogger, '_audit_file', log_file):
            logger = AuditLogger.__new__(AuditLogger)
            logger._initialized = False
            logger._log_dir = tmp_path

            result = logger.get_recent_logs()
            assert result == []

    def test_get_recent_logs(self, tmp_path):
        from src.security_manager import AuditLogger

        log_file = tmp_path / "audit.log"
        log_file.write_text('{"user_id": "u1", "action": "A", "resource": "r", "details": ""}\n'
                            '{"user_id": "u2", "action": "B", "resource": "s", "details": ""}\n')

        with patch.object(AuditLogger, '_audit_file', log_file):
            logger = AuditLogger.__new__(AuditLogger)
            logger._initialized = False
            logger._log_dir = tmp_path

            result = logger.get_recent_logs(limit=10)
            assert len(result) == 2


class TestGDPRManager:
    """Tests for GDPRManager"""

    def test_export_user_data(self, tmp_path):
        from src.security_manager import GDPRManager, _USER_DATA_STORE

        _USER_DATA_STORE.clear()
        _USER_DATA_STORE["user1"] = {"name": "Test User"}

        with patch('src.security_manager.AuditLogger') as mock_audit:
            mock_logger = MagicMock()
            mock_audit.return_value = mock_logger

            result = GDPRManager.export_user_data("user1")

            assert result["user_id"] == "user1"
            assert "exported_data" in result
            mock_logger.log.assert_called_once()

    def test_delete_user_data(self, tmp_path):
        from src.security_manager import GDPRManager, _USER_DATA_STORE

        _USER_DATA_STORE.clear()
        _USER_DATA_STORE["user1"] = {"name": "Test User"}

        with patch('src.security_manager.AuditLogger') as mock_audit:
            mock_logger = MagicMock()
            mock_audit.return_value = mock_logger

            result = GDPRManager.delete_user_data("user1")

            assert result is True
            assert "user1" not in _USER_DATA_STORE
            mock_logger.log.assert_called_once()

    def test_delete_user_data_not_found(self, tmp_path):
        from src.security_manager import GDPRManager, _USER_DATA_STORE

        _USER_DATA_STORE.clear()

        with patch('src.security_manager.AuditLogger') as mock_audit:
            mock_logger = MagicMock()
            mock_audit.return_value = mock_logger

            result = GDPRManager.delete_user_data("nonexistent")
            assert result is False

    def test_register_data(self, tmp_path):
        from src.security_manager import GDPRManager, _USER_DATA_STORE

        _USER_DATA_STORE.clear()

        GDPRManager.register_data("user1", "profile", {"name": "Test"})
        assert "user1" in _USER_DATA_STORE
        assert _USER_DATA_STORE["user1"]["profile"] == {"name": "Test"}

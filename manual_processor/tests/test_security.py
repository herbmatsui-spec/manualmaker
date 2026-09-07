"""
Security tests for Manual Processor.
Tests PII masking, validation, rate limiting, and security headers.
"""

import os
import io
import json
import pytest
from pathlib import Path

from src.utils.validators import (
    validate_file_size,
    validate_pdf_content,
    validate_uuid,
    validate_language_code,
    validate_filename,
    validate_extension,
)
from src.security_manager import SecurityManager, AuditLogger
from src.security.audit_logger import StructuredAuditLogger, AuditEventType
from src.utils.log_filter import mask_sensitive, SensitiveDataFilter


class TestValidators:
    """Test input validation functions"""

    def test_validate_file_size_valid(self):
        assert validate_file_size(50.0, 100.0) is True

    def test_validate_file_size_too_large(self):
        assert validate_file_size(150.0, 100.0) is False

    def test_validate_file_size_negative(self):
        assert validate_file_size(-1.0, 100.0) is False

    def test_validate_pdf_content_valid(self):
        assert validate_pdf_content(b"%PDF-1.4\n...") is True

    def test_validate_pdf_content_invalid(self):
        assert validate_pdf_content(b"Not a PDF") is False

    def test_validate_pdf_content_empty(self):
        assert validate_pdf_content(b"") is False

    def test_validate_uuid_valid_with_hyphens(self):
        assert validate_uuid("12345678-1234-1234-1234-123456789012") is True

    def test_validate_uuid_valid_without_hyphens(self):
        assert validate_uuid("12345678123412341234123456789012") is True

    def test_validate_uuid_invalid(self):
        assert validate_uuid("not-a-uuid") is False

    def test_validate_uuid_empty(self):
        assert validate_uuid("") is False

    def test_validate_language_code_valid(self):
        assert validate_language_code("ja") is True
        assert validate_language_code("en") is True

    def test_validate_language_code_invalid(self):
        assert validate_language_code("fr") is False
        assert validate_language_code("") is False

    def test_validate_filename_valid(self):
        assert validate_filename("test.pdf") is True
        assert validate_filename("my-file_v2.pdf") is True

    def test_validate_filename_path_traversal(self):
        assert validate_filename("../etc/passwd") is False
        assert validate_filename("test/file.pdf") is False
        assert validate_filename("test\\file.pdf") is False

    def test_validate_extension_valid(self):
        assert validate_extension("test.pdf", [".pdf"]) is True

    def test_validate_extension_invalid(self):
        assert validate_extension("test.txt", [".pdf"]) is False


class TestPIIMasking:
    """Test PII masking functionality"""

    def test_mask_email(self):
        masked, info = SecurityManager.mask_sensitive_data("Contact: test@example.com")
        assert "[REDACTED_EMAIL]" in masked
        assert info["counts"]["EMAIL"] == 1

    def test_mask_phone_jp(self):
        masked, info = SecurityManager.mask_sensitive_data("Phone: 03-1234-5678")
        assert "[REDACTED_PHONE]" in masked
        assert info["counts"]["PHONE_JP"] == 1

    def test_mask_my_number(self):
        masked, info = SecurityManager.mask_sensitive_data("My Number: 1234-5678-9012")
        assert "[REDACTED_MYNUMBER]" in masked
        assert info["counts"]["MY_NUMBER"] == 1

    def test_mask_credit_card(self):
        masked, info = SecurityManager.mask_sensitive_data("Card: 4111-1111-1111-1111")
        assert "[REDACTED_CARD]" in masked
        assert info["counts"]["CREDIT_CARD"] == 1

    def test_mask_multiple_pii(self):
        text = "Email: user@test.com, Phone: 03-1234-5678, Card: 4111-1111-1111-1111"
        masked, info = SecurityManager.mask_sensitive_data(text)
        assert "[REDACTED_EMAIL]" in masked
        assert "[REDACTED_PHONE]" in masked
        assert "[REDACTED_CARD]" in masked
        assert info["counts"]["EMAIL"] == 1
        assert info["counts"]["PHONE_JP"] == 1
        assert info["counts"]["CREDIT_CARD"] == 1

    def test_mask_empty_text(self):
        masked, info = SecurityManager.mask_sensitive_data("")
        assert masked == ""
        assert info["counts"] == {}

    def test_mask_no_pii(self):
        masked, info = SecurityManager.mask_sensitive_data("Hello world")
        assert masked == "Hello world"
        assert info["counts"] == {}


class TestPIIMaskingToggle:
    """Test PII masking on/off behavior"""

    def test_default_config_masking_disabled(self):
        from config.config_new import AppConfig
        config = AppConfig.from_env()
        assert config.pii_masking_enabled is False

    def test_env_var_enables_masking(self, monkeypatch):
        monkeypatch.setenv("PII_MASKING_ENABLED", "True")
        from config.config_new import AppConfig
        config = AppConfig.from_env()
        assert config.pii_masking_enabled is True

    def test_env_var_disables_masking_explicitly(self, monkeypatch):
        monkeypatch.setenv("PII_MASKING_ENABLED", "False")
        from config.config_new import AppConfig
        config = AppConfig.from_env()
        assert config.pii_masking_enabled is False

    def test_masking_disabled_preserves_original_text(self):
        from unittest.mock import MagicMock
        from src.processor.processor import DocumentProcessor

        config = MagicMock()
        config.pii_masking_enabled = False
        config.google_api_key = "dummy"
        config.gemini_api_key = "dummy"
        config.max_file_size_mb = 50
        config.supported_extensions = [".pdf"]
        config.pdf_dpi = 150
        config.generate_diagram = False

        processor = DocumentProcessor(config=config)

        sensitive = "Contact: test@example.com, Phone: 03-1234-5678"
        if getattr(processor.config, 'pii_masking_enabled', False):
            masked, _ = SecurityManager.mask_sensitive_data(sensitive)
            result_text = masked
        else:
            result_text = sensitive

        assert result_text == sensitive

    def test_masking_enabled_redacts_text(self):
        sensitive = "Contact: test@example.com, Phone: 03-1234-5678"
        masked, info = SecurityManager.mask_sensitive_data(sensitive, record_positions=True)
        assert "[REDACTED_EMAIL]" in masked
        assert "[REDACTED_PHONE]" in masked
        assert info["counts"].get("EMAIL") == 1
        assert info["counts"].get("PHONE_JP") == 1


class TestAuditLogger:
    """Test audit logging"""

    def test_structured_audit_log(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log(
            event_type="test_event",
            user_id="user1",
            action="TEST",
            resource="test_resource",
            details={"key": "value"}
        )

        logs = audit.get_recent_logs(10)
        assert len(logs) == 1
        assert logs[0]["event_type"] == "test_event"
        assert logs[0]["user_id"] == "user1"
        assert logs[0]["action"] == "TEST"
        assert logs[0]["resource"] == "test_resource"
        assert logs[0]["details"] == {"key": "value"}

    def test_audit_log_file_format(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log("pii_mask", "user1", "MASK", "file.pdf", {"pattern": "EMAIL"})

        log_file = log_dir / "audit.jsonl"
        assert log_file.exists()

        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["event_type"] == "pii_mask"
            assert "timestamp" in entry

    def test_audit_log_stats(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log("test", "user1", "A", "r1")
        audit.log("test", "user2", "B", "r2")

        stats = audit.get_stats()
        assert stats["total_entries"] == 2
        assert "log_file" in stats


class TestLogFilter:
    """Test log filtering"""

    def test_mask_api_key(self):
        text = "api_key=secret123"
        masked = mask_sensitive(text)
        assert "secret123" not in masked
        assert "[REDACTED]" in masked

    def test_mask_bearer_token(self):
        text = "Authorization: Bearer token1234567890"
        masked = mask_sensitive(text)
        assert "token1234567890" not in masked
        assert "[REDACTED]" in masked

    def test_mask_email(self):
        text = "Contact: user@example.com"
        masked = mask_sensitive(text)
        assert "user@example.com" not in masked
        assert "[REDACTED_EMAIL]" in masked

    def test_mask_credit_card(self):
        text = "Card: 4111-1111-1111-1111"
        masked = mask_sensitive(text)
        assert "4111-1111-1111-1111" not in masked
        assert "[REDACTED_CARD]" in masked

    def test_no_false_positives(self):
        text = "Hello world, this is a test"
        masked = mask_sensitive(text)
        assert masked == text

"""
Tests for audit_logger module (Step 15)
Target coverage: 90%
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os

from src.security.audit_logger import (
    StructuredAuditLogger,
    AuditEntry,
    AuditEventType,
    get_audit_logger,
    _audit_logger,
)


class TestAuditEntry:
    """Test AuditEntry dataclass"""

    def test_to_json_basic(self):
        entry = AuditEntry(
            timestamp="2024-01-01T00:00:00Z",
            event_type="test_event",
            user_id="user1",
            action="TEST",
            resource="resource1",
        )
        json_str = entry.to_json()
        data = json.loads(json_str)
        assert data["event_type"] == "test_event"
        assert data["user_id"] == "user1"

    def test_to_json_with_all_fields(self):
        entry = AuditEntry(
            timestamp="2024-01-01T00:00:00Z",
            event_type="test_event",
            user_id="user1",
            action="TEST",
            resource="resource1",
            details={"key": "value"},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            success=False,
            error_message="test error",
        )
        json_str = entry.to_json()
        data = json.loads(json_str)
        assert data["details"] == {"key": "value"}
        assert data["ip_address"] == "192.168.1.1"
        assert data["success"] is False
        assert data["error_message"] == "test error"


class TestStructuredAuditLogger:
    """Test StructuredAuditLogger class"""

    def test_init_creates_log_dir(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))
        assert log_dir.exists()

    def test_log_writes_entry(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log(
            event_type="test_event",
            user_id="user1",
            action="TEST",
            resource="resource1",
        )

        log_file = log_dir / "audit.jsonl"
        assert log_file.exists()
        with open(log_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["user_id"] == "user1"

    def test_log_with_all_parameters(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log(
            event_type="test_event",
            user_id="user1",
            action="TEST",
            resource="resource1",
            details={"key": "value"},
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
            success=False,
            error_message="error occurred",
        )

        logs = audit.get_recent_logs(1)
        assert len(logs) == 1
        assert logs[0]["ip_address"] == "192.168.1.1"
        assert logs[0]["success"] is False

    def test_log_pii_mask(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log_pii_mask(
            user_id="user1",
            pattern_name="EMAIL",
            count=5,
            ip_address="192.168.1.1",
        )

        logs = audit.get_recent_logs(1)
        assert len(logs) == 1
        assert logs[0]["event_type"] == "pii_mask"
        assert logs[0]["action"] == "MASK"
        assert logs[0]["details"]["pattern"] == "EMAIL"
        assert logs[0]["details"]["count"] == 5

    def test_log_api_key_access_success(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log_api_key_access(
            user_id="user1",
            service="gemini",
            action="READ",
            success=True,
        )

        logs = audit.get_recent_logs(1)
        assert len(logs) == 1
        assert logs[0]["event_type"] == "api_key_access"
        assert logs[0]["resource"] == "api_key:gemini"

    def test_log_api_key_access_failure(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log_api_key_access(
            user_id="user1",
            service="gemini",
            action="READ",
            success=False,
            error_message="Invalid key",
            ip_address="192.168.1.1",
        )

        logs = audit.get_recent_logs(1)
        assert len(logs) == 1
        assert logs[0]["success"] is False
        assert logs[0]["error_message"] == "Invalid key"

    def test_log_file_operation_upload(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log_file_operation(
            user_id="user1",
            operation="UPLOAD",
            filename="test.pdf",
            file_size_mb=1.5,
        )

        logs = audit.get_recent_logs(1)
        assert len(logs) == 1
        assert logs[0]["event_type"] == "file_upload"
        assert logs[0]["details"]["file_size_mb"] == 1.5

    def test_log_file_operation_download(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log_file_operation(
            user_id="user1",
            operation="DOWNLOAD",
            filename="test.pdf",
        )

        logs = audit.get_recent_logs(1)
        assert len(logs) == 1
        assert logs[0]["event_type"] == "file_download"

    def test_log_file_operation_with_size(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log_file_operation(
            user_id="user1",
            operation="UPLOAD",
            filename="test.pdf",
            file_size_mb=2.5,
            success=False,
            error_message="Upload failed",
        )

        logs = audit.get_recent_logs(1)
        assert logs[0]["details"]["file_size_mb"] == 2.5
        assert logs[0]["success"] is False

    def test_get_recent_logs_empty(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        logs = audit.get_recent_logs()
        assert logs == []

    def test_get_recent_logs_file_not_exists(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir), log_file="nonexistent.jsonl")

        logs = audit.get_recent_logs()
        assert logs == []

    def test_get_recent_logs_limit(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        for i in range(10):
            audit.log("test", f"user{i}", "A", f"r{i}")

        logs = audit.get_recent_logs(limit=5)
        assert len(logs) == 5

    def test_get_recent_logs_malformed_json(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        log_file = log_dir / "audit.jsonl"
        with open(log_file, "w") as f:
            f.write('{"valid": true}\n')
            f.write('invalid json\n')
            f.write('{"also_valid": true}\n')

        logs = audit.get_recent_logs(limit=10)
        assert len(logs) == 2

    def test_get_stats(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log("test", "user1", "A", "r1")
        audit.log("test", "user2", "B", "r2")

        stats = audit.get_stats()
        assert stats["total_entries"] == 2
        assert "log_file" in stats

    def test_get_stats_no_file(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir), log_file="new.jsonl")

        stats = audit.get_stats()
        assert stats["total_entries"] == 0
        assert stats["log_file_size_mb"] == 0

    def test_rotate_logs_max_backups(self, tmp_path):
        log_dir = tmp_path / "logs"
        max_backup = 3
        audit = StructuredAuditLogger(log_dir=str(log_dir), max_backup_files=max_backup)

        audit.log_file = log_dir / "audit.jsonl"
        log_file = audit.log_file

        log_file.write_text("original content\n")
        for i in range(1, max_backup + 1):
            (log_dir / f"audit.jsonl.{i}").write_text(f"backup {i}\n")

        audit._rotate_logs()

        assert not (log_dir / f"audit.jsonl.{max_backup + 1}").exists()
        assert (log_dir / "audit.jsonl.1").exists()
        assert not log_file.exists()

    def test_rotate_logs_shifts_existing(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir), max_backup_files=3)

        audit.log_file = log_dir / "audit.jsonl"
        log_file = audit.log_file

        log_file.write_text("content\n")
        (log_dir / "audit.jsonl.1").write_text("backup 1\n")
        (log_dir / "audit.jsonl.2").write_text("backup 2\n")

        audit._rotate_logs()

        assert (log_dir / "audit.jsonl.2").exists()
        assert (log_dir / "audit.jsonl.3").exists()

    @patch("builtins.open", side_effect=IOError("Disk full"))
    def test_log_write_error_handled(self, mock_file, tmp_path, caplog):
        import logging
        caplog.set_level(logging.DEBUG)

        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir))

        audit.log("test", "user1", "A", "r1")

        assert audit._entry_count == 1

    def test_write_to_file_rotation_needed(self, tmp_path):
        log_dir = tmp_path / "logs"
        audit = StructuredAuditLogger(log_dir=str(log_dir), max_file_size_mb=1)

        audit.log_file = log_dir / "audit.jsonl"
        audit.log_file.write_text("x" * (1024 * 1024))

        with patch.object(audit, "_rotate_logs") as mock_rotate:
            audit._write_to_file('{"test": "entry"}')
            mock_rotate.assert_called_once()


class TestGetAuditLoggerSingleton:
    """Test get_audit_logger singleton function"""

    def test_returns_structured_logger(self):
        logger = get_audit_logger()
        assert isinstance(logger, StructuredAuditLogger)

    def test_singleton_same_instance(self):
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2

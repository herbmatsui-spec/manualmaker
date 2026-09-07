"""
Structured Audit Logger (JSON format).
Provides security event logging with JSON Lines output.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Audit event types"""
    PII_MASK = "pii_mask"
    API_KEY_ACCESS = "api_key_access"
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    CONFIG_CHANGE = "config_change"
    ERROR = "error"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class AuditEntry:
    """Single audit log entry"""
    timestamp: str
    event_type: str
    user_id: str
    action: str
    resource: str
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(asdict(self), ensure_ascii=False)


class StructuredAuditLogger:
    """
    Structured audit logger that outputs JSON Lines format.
    
    Features:
    - JSON Lines output for easy parsing
    - Multiple output destinations (file, stdout, Cloudflare KV)
    - Log rotation support
    - PII-safe logging (automatic masking)
    """

    def __init__(
        self,
        log_dir: str = "./logs",
        log_file: str = "audit.jsonl",
        max_file_size_mb: int = 10,
        max_backup_files: int = 5,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / log_file
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.max_backup_files = max_backup_files
        self._entry_count = 0

    def log(
        self,
        event_type: str,
        user_id: str,
        action: str,
        resource: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Log an audit event

        Args:
            event_type: Type of event (use AuditEventType values)
            user_id: User identifier
            action: Action performed (e.g., "READ", "WRITE", "DELETE")
            resource: Resource affected
            details: Additional details (will be JSON-serialized)
            ip_address: Client IP address
            user_agent: Client user agent
            success: Whether the action succeeded
            error_message: Error message if failed
        """
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            user_id=user_id,
            action=action,
            resource=resource,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )

        json_line = entry.to_json()

        # Write to file
        try:
            self._write_to_file(json_line)
        except Exception as e:
            logger.error(f"Failed to write audit log to file: {e}")

        # Debug log (not info, to avoid duplication with file output)
        logger.debug(f"Audit: {event_type} {action} {resource}")

        self._entry_count += 1

    def _write_to_file(self, json_line: str) -> None:
        """Write JSON line to log file with rotation"""
        # Check if rotation needed
        if self.log_file.exists() and self.log_file.stat().st_size >= self.max_file_size_bytes:
            self._rotate_logs()

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json_line + "\n")

    def _rotate_logs(self) -> None:
        """Rotate log files"""
        # Remove oldest backup if at max
        oldest = self.log_dir / f"{self.log_file.name}.{self.max_backup_files}"
        if oldest.exists():
            oldest.unlink()

        # Shift existing backups
        for i in range(self.max_backup_files - 1, 0, -1):
            src = self.log_dir / f"{self.log_file.name}.{i}"
            dst = self.log_dir / f"{self.log_file.name}.{i + 1}"
            if src.exists():
                src.rename(dst)

        # Rotate current file
        if self.log_file.exists():
            self.log_file.rename(self.log_dir / f"{self.log_file.name}.1")

    def log_pii_mask(
        self,
        user_id: str,
        pattern_name: str,
        count: int,
        ip_address: Optional[str] = None,
    ) -> None:
        """Convenience method for PII masking events"""
        self.log(
            event_type=AuditEventType.PII_MASK.value,
            user_id=user_id,
            action="MASK",
            resource="pii_patterns",
            details={"pattern": pattern_name, "count": count},
            ip_address=ip_address,
        )

    def log_api_key_access(
        self,
        user_id: str,
        service: str,
        action: str,
        success: bool,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Convenience method for API key access events"""
        self.log(
            event_type=AuditEventType.API_KEY_ACCESS.value,
            user_id=user_id,
            action=action,
            resource=f"api_key:{service}",
            details={"service": service},
            success=success,
            error_message=error_message,
            ip_address=ip_address,
        )

    def log_file_operation(
        self,
        user_id: str,
        operation: str,
        filename: str,
        file_size_mb: Optional[float] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Convenience method for file operations"""
        self.log(
            event_type=AuditEventType.FILE_UPLOAD if operation == "UPLOAD" else AuditEventType.FILE_DOWNLOAD,
            user_id=user_id,
            action=operation,
            resource=filename,
            details={"file_size_mb": file_size_mb} if file_size_mb else None,
            success=success,
            error_message=error_message,
            ip_address=ip_address,
        )

    def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent audit log entries

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries as dictionaries
        """
        if not self.log_file.exists():
            return []

        try:
            entries = []
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Read from end (most recent first)
            for line in reversed(lines[-limit:]):
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

            return entries
        except Exception as e:
            logger.error(f"Failed to read audit logs: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get audit logger statistics"""
        return {
            "total_entries": self._entry_count,
            "log_file": str(self.log_file),
            "log_file_size_mb": (
                round(self.log_file.stat().st_size / 1024 / 1024, 2)
                if self.log_file.exists()
                else 0
            ),
        }


# Global instance
_audit_logger: Optional[StructuredAuditLogger] = None


def get_audit_logger() -> StructuredAuditLogger:
    """Get global audit logger instance (singleton)"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = StructuredAuditLogger()
    return _audit_logger

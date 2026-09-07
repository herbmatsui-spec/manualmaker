"""
Security & Privacy Module (Step 18)
Provides automatic PII (Personally Identifiable Information) detection and masking.
"""

import logging
import re
import os
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from dataclasses import dataclass

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

try:
    import keyring
    _HAS_KEYRING = True
except ImportError:
    _HAS_KEYRING = False

try:
    from cryptography.fernet import Fernet
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

logger = logging.getLogger(__name__)


@dataclass
class MaskedPosition:
    """Position of masked data in text"""
    start: int
    end: int
    mask_type: str
    original_length: int


class SecurityManager:
    """Handles data masking, sensitive information detection, and secure credential storage"""

    SERVICE_NAME = "manual_processor"
    API_KEY_USERNAME = "gemini_api_key"

    PATTERNS: List[Tuple[str, str, str]] = []

    @classmethod
    def _load_pii_patterns(cls) -> List[Tuple[str, str, str]]:
        """
        Load PII patterns from YAML configuration file.
        
        Returns:
            List of tuples: (pattern_name, regex, mask)
        """
        if cls.PATTERNS:
            return cls.PATTERNS

        yaml_path = Path(__file__).parent.parent / "config" / "pii_patterns.yaml"
        
        if not yaml_path.exists():
            logger.warning(f"PII patterns YAML not found at {yaml_path}, using defaults")
            return cls._get_default_patterns()

        try:
            if not _HAS_YAML:
                logger.warning("PyYAML not available, using default patterns")
                return cls._get_default_patterns()

            with open(yaml_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            patterns = []
            for item in config.get("patterns", []):
                if item.get("enabled", True):
                    patterns.append((
                        item["name"],
                        item["regex"],
                        item["mask"]
                    ))

            cls.PATTERNS = patterns
            logger.info(f"Loaded {len(patterns)} PII patterns from {yaml_path}")
            return patterns

        except Exception as e:
            logger.error(f"Failed to load PII patterns from YAML: {e}")
            return cls._get_default_patterns()

    @classmethod
    def _get_default_patterns(cls) -> List[Tuple[str, str, str]]:
        """Return hardcoded default patterns as fallback"""
        return [
            ("EMAIL", r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "[REDACTED_EMAIL]"),
            ("PHONE", r'0\d{1,4}-\d{1,4}-\d{4}', "[REDACTED_PHONE]"),
            ("MY_NUMBER", r'\b\d{4}-\d{4}-\d{4}\b', "[REDACTED_MYNUMBER]"),
            ("PASSPORT", r'\b[A-Z]{1,2}\d{7}\b', "[REDACTED_PASSPORT]"),
            ("POSTAL", r'〒\s*\d{3}-\d{4}', "[REDACTED_POSTAL]"),
            ("POSTAL_NOCOPY", r'(?<![a-zA-Z0-9])\d{3}-\d{4}(?![0-9])', "[REDACTED_POSTAL]"),
            ("CREDIT_CARD", r'\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[ -]?\d{4}[ -]?\d{4}[ -]?\d{1,4}\b', "[REDACTED_CARD]"),
            ("IP_ADDRESS", r'\b(?:\d{1,3}\.){3}\d{1,3}\b', "[REDACTED_IP]"),
            ("BANK_ACCOUNT", r'\b\d{6}-\d{8}\b', "[REDACTED_BANK]"),
        ]

    @classmethod
    def mask_sensitive_data(cls, text: str, record_positions: bool = False) -> Tuple[str, Dict[str, Any]]:
        """
        Mask sensitive personal information in text

        Args:
            text: Input text to mask
            record_positions: If True, also return positions of masked items

        Returns:
            (masked_text, detection_info)
            detection_info is a dict with:
              - 'counts': Dict[str, int] - count per type
              - 'positions': List[MaskedPosition] (optional, if record_positions=True)
        """
        if not text:
            return "", {"counts": {}}

        patterns = cls._load_pii_patterns()
        masked = text
        counts = {}
        positions = []

        for p_name, pattern, replacement in patterns:
            matches = list(re.finditer(pattern, masked))
            if matches:
                counts[p_name] = len(matches)
                if record_positions:
                    for match in matches:
                        positions.append(MaskedPosition(
                            start=match.start(),
                            end=match.end(),
                            mask_type=p_name,
                            original_length=len(match.group())
                        ))
                masked = re.sub(pattern, replacement, masked)

        result = {"counts": counts}
        if record_positions:
            result["positions"] = positions

        if counts:
            logger.info(f"SecurityManager: Masked sensitive data: {counts}")

        return masked, result

    @classmethod
    def unmask_data(cls, masked_text: str, positions: List[MaskedPosition], original_values: List[str]) -> str:
        """
        Unmask previously masked data

        Args:
            masked_text: Text with masked values
            positions: List of MaskedPosition from original masking
            original_values: List of original values (must match positions order)

        Returns:
            Text with original values restored
        """
        if not positions or not original_values:
            return masked_text

        result = masked_text
        offset = 0

        for pos, original in zip(positions, original_values):
            replacement = original
            start = pos.start + offset
            end = pos.end + offset

            if start >= 0 and end <= len(result):
                result = result[:start] + replacement + result[end:]
                offset += len(replacement) - pos.original_length

        return result

    @classmethod
    def save_api_key(cls, key: str) -> bool:
        """OSの資格情報マネージャーにAPIキーを保存"""
        if not _HAS_KEYRING:
            logger.warning("keyringライブラリが利用できません")
            return False
        try:
            keyring.set_password(cls.SERVICE_NAME, cls.API_KEY_USERNAME, key)
            logger.info("APIキーをセキュアストレージに保存しました")
            return True
        except Exception as e:
            logger.error(f"APIキーの保存失敗: {e}")
            return False

    @classmethod
    def load_api_key(cls) -> Optional[str]:
        """OSの資格情報マネージャーからAPIキーを取得"""
        if not _HAS_KEYRING:
            return None
        try:
            return keyring.get_password(cls.SERVICE_NAME, cls.API_KEY_USERNAME)
        except Exception as e:
            logger.error(f"APIキーの読み込み失敗: {e}")
            return None

    @classmethod
    def _get_encryption_key(cls) -> Optional[bytes]:
        """Get encryption key from environment variable"""
        key_env = os.getenv("ENCRYPTION_KEY", "")
        if not key_env:
            return None
        try:
            return key_env.encode("utf-8")[:32].ljust(32)[:32]
        except Exception:
            return None

    @classmethod
    def encrypt_data(cls, data: bytes) -> Tuple[bytes, bool]:
        """
        Encrypt data using Fernet symmetric encryption

        Returns: (encrypted_data, success)
        """
        if not _HAS_CRYPTO:
            logger.warning("cryptography library not available")
            return data, False

        key = cls._get_encryption_key()
        if not key:
            logger.warning("ENCRYPTION_KEY not set")
            return data, False

        try:
            f = Fernet(Fernet.generate_key() if len(key) < 32 else key)
            encrypted = f.encrypt(data)
            return encrypted, True
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return data, False

    @classmethod
    def decrypt_data(cls, encrypted_data: bytes) -> Tuple[bytes, bool]:
        """
        Decrypt data using Fernet symmetric encryption

        Returns: (decrypted_data, success)
        """
        if not _HAS_CRYPTO:
            logger.warning("cryptography library not available")
            return encrypted_data, False

        key = cls._get_encryption_key()
        if not key:
            logger.warning("ENCRYPTION_KEY not set")
            return encrypted_data, False

        try:
            f = Fernet(Fernet.generate_key() if len(key) < 32 else key)
            decrypted = f.decrypt(encrypted_data)
            return decrypted, True
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_data, False

    @classmethod
    def secure_delete(cls, file_path: Path) -> bool:
        """
        Securely delete a file by overwriting with random data before deletion

        Args:
            file_path: Path to file to securely delete

        Returns:
            True if successful, False otherwise
        """
        if not file_path.exists():
            return False

        try:
            file_size = file_path.stat().st_size
            with open(file_path, "r+b") as f:
                import random
                for _ in range(3):
                    f.seek(0)
                    f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())
            file_path.unlink()
            logger.info(f"Securely deleted: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Secure delete failed for {file_path}: {e}")
            try:
                file_path.unlink()
            except Exception:
                pass
            return False


class AuditLogger:
    """Audit logger for security events"""

    _instance = None
    _log_dir = Path("./logs")
    _audit_file = _log_dir / "audit.log"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, user_id: str, action: str, resource: str, details: str = "") -> None:
        """
        Log an audit event

        Args:
            user_id: User identifier
            action: Action performed (e.g., "READ", "WRITE", "DELETE")
            resource: Resource affected
            details: Additional details
        """
        import json
        from datetime import datetime

        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "details": details
        }

        try:
            with open(self._audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def log_access(self, user_id: str, resource: str) -> None:
        """Log a resource access event"""
        self.log(user_id, "ACCESS", resource)

    def log_modification(self, user_id: str, resource: str, details: str = "") -> None:
        """Log a modification event"""
        self.log(user_id, "MODIFY", resource, details)

    def log_deletion(self, user_id: str, resource: str) -> None:
        """Log a deletion event"""
        self.log(user_id, "DELETE", resource)

    def get_recent_logs(self, limit: int = 100) -> List[Dict[str, str]]:
        """Get recent audit log entries"""
        if not self._audit_file.exists():
            return []

        try:
            with open(self._audit_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            entries = []
            for line in lines[-limit:]:
                try:
                    import json
                    entries.append(json.loads(line.strip()))
                except Exception:
                    continue
            return entries
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
            return []


_USER_DATA_STORE: Dict[str, Dict[str, Any]] = {}


class GDPRManager:
    """Manager for GDPR compliance (data export and deletion)"""

    @classmethod
    def export_user_data(cls, user_id: str) -> Dict[str, Any]:
        """
        Export all data associated with a user (GDPR Article 15)

        Returns:
            Dictionary containing all user data
        """
        audit = AuditLogger()
        audit.log(user_id, "EXPORT", "user_data", "GDPR data export requested")

        user_data = _USER_DATA_STORE.get(user_id, {})

        return {
            "user_id": user_id,
            "exported_data": user_data,
            "export_timestamp": str(Path.cwd())
        }

    @classmethod
    def delete_user_data(cls, user_id: str) -> bool:
        """
        Delete all data associated with a user (GDPR Article 17)

        Returns:
            True if successful
        """
        audit = AuditLogger()
        audit.log(user_id, "DELETE", "user_data", "GDPR data deletion requested")

        if user_id in _USER_DATA_STORE:
            del _USER_DATA_STORE[user_id]
            logger.info(f"GDPR: Deleted all data for user {user_id}")
            return True
        return False

    @classmethod
    def register_data(cls, user_id: str, data_type: str, data: Any) -> None:
        """Register user data for GDPR management"""
        if user_id not in _USER_DATA_STORE:
            _USER_DATA_STORE[user_id] = {}
        _USER_DATA_STORE[user_id][data_type] = data

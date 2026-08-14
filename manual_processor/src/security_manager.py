"""
Security & Privacy Module (Step 18)
Provides automatic PII (Personally Identifiable Information) detection and masking.
"""

import logging
import re
from typing import Dict, List, Tuple, Optional

try:
    import keyring
    _HAS_KEYRING = True
except ImportError:
    _HAS_KEYRING = False

logger = logging.getLogger(__name__)


class SecurityManager:
    """Handles data masking, sensitive information detection, and secure credential storage"""

    SERVICE_NAME = "manual_processor"
    API_KEY_USERNAME = "gemini_api_key"

    # Patterns for Japanese phone numbers, emails, postal codes, credit cards, IP addresses
    PATTERNS: List[Tuple[str, str, str]] = [
        ("EMAIL", r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "[REDACTED_EMAIL]"),
        ("PHONE", r'0\d{1,4}-\d{1,4}-\d{4}', "[REDACTED_PHONE]"),
        ("POSTAL", r'〒?\s*\d{3}-\d{4}', "[REDACTED_POSTAL]"),
        ("CREDIT_CARD", r'\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[ -]?\d{4}[ -]?\d{4}[ -]?\d{1,4}\b', "[REDACTED_CARD]"),
        ("IP_ADDRESS", r'\b(?:\d{1,3}\.){3}\d{1,3}\b', "[REDACTED_IP]"),
    ]

    @classmethod
    def mask_sensitive_data(cls, text: str) -> Tuple[str, Dict[str, int]]:
        """
        Mask sensitive personal information in text
        Returns (masked_text, detection_counts)
        """
        if not text:
            return "", {}

        masked = text
        counts = {}

        for p_name, pattern, replacement in cls.PATTERNS:
            matches = re.findall(pattern, masked)
            if matches:
                counts[p_name] = len(matches)
                masked = re.sub(pattern, replacement, masked)

        if counts:
            logger.info(f"SecurityManager: Masked sensitive data: {counts}")

        return masked, counts

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

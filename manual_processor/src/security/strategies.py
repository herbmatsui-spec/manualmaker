"""
Security backend strategies implementing the interfaces from interfaces.py
Provides concrete implementations for different environments.
"""
import os
import re
import yaml
import logging
import keyring
from typing import List, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass

try:
    from cryptography.fernet import Fernet
    _HAS_FERNET = True
except ImportError:
    _HAS_FERNET = False

from .interfaces import PatternProvider, KeyStore, EncryptionProvider, MaskedPosition

logger = logging.getLogger(__name__)


@dataclass
class HardcodedPatternProvider(PatternProvider):
    """ハードコードされたデフォルトPIIパターンを提供"""
    
    def load_patterns(self) -> List[Tuple[str, str, str]]:
        """SecurityManagerの_get_default_patterns()と同じパターンを返す"""
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


class EnvVarKeyStore(KeyStore):
    """環境変数を使ったAPIキー保存（フォールバック用）"""
    
    _ENV_PREFIX = "MANUAL_PROCESSOR_"
    
    def get(self, service: str, username: str) -> Optional[str]:
        """環境変数からAPIキーを取得"""
        env_var = f"{self._ENV_PREFIX}{service.upper()}_{username.upper()}"
        return os.environ.get(env_var)
    
    def set(self, service: str, username: str, value: str) -> None:
        """環境変数にAPIキーを保存（実行時のみ有効）"""
        env_var = f"{self._ENV_PREFIX}{service.upper()}_{username.upper()}"
        os.environ[env_var] = value
        logger.warning(f"API key stored in environment variable {env_var} (not persistent)")
    
    def delete(self, service: str, username: str) -> None:
        """環境変数からAPIキーを削除"""
        env_var = f"{self._ENV_PREFIX}{service.upper()}_{username.upper()}"
        os.environ.pop(env_var, None)


class NoOpEncryption(EncryptionProvider):
    """暗号化を行わない戦略（開発・テスト用または暗号化キー未設定時）"""
    
    def encrypt(self, data: bytes) -> Tuple[bytes, bool]:
        """データを変更せず返す（暗号化なし）"""
        logger.warning("Encryption disabled - returning data unchanged")
        return data, False
    
    def decrypt(self, encrypted_data: bytes) -> Tuple[bytes, bool]:
        """データを変更せず返す（復号なし）"""
        logger.warning("Decryption disabled - returning data unchanged")
        return encrypted_data, False


class FernetEncryption(EncryptionProvider):
    """Fernet symmetric encryption using key from environment variable"""
    
    def __init__(self):
        self._fernet = None
        self._init_fernet()
    
    def _init_fernet(self) -> None:
        """Initialize Fernet from environment variable"""
        if not _HAS_FERNET:
            return
        
        key_env = os.getenv("ENCRYPTION_KEY", "")
        if not key_env:
            return
        
        try:
            import base64
            # Try to decode as base64 first (for proper Fernet keys)
            try:
                key = base64.urlsafe_b64decode(key_env)
                if len(key) == 32:
                    self._fernet = Fernet(key_env)  # Fernet expects base64-encoded key
                    return
            except Exception:
                pass
            
            # Fallback: treat as raw key, encode to bytes
            key = key_env.encode("utf-8")[:32].ljust(32)[:32]
            if len(key) >= 32:
                # Convert to base64 for Fernet
                key_b64 = base64.urlsafe_b64encode(key).decode()
                self._fernet = Fernet(key_b64)
            else:
                # Key too short, generate a new one (but this won't be persistent)
                self._fernet = Fernet(Fernet.generate_key())
        except Exception as e:
            logger.error(f"Failed to initialize Fernet: {e}")
            self._fernet = None
    
    def encrypt(self, data: bytes) -> Tuple[bytes, bool]:
        """Encrypt data using Fernet"""
        if not self._fernet:
            logger.warning("Fernet key not available")
            return data, False
        
        try:
            encrypted = self._fernet.encrypt(data)
            return encrypted, True
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return data, False
    
    def decrypt(self, encrypted_data: bytes) -> Tuple[bytes, bool]:
        """Decrypt data using Fernet"""
        if not self._fernet:
            logger.warning("Fernet key not available")
            return encrypted_data, False
        
        try:
            decrypted = self._fernet.decrypt(encrypted_data)
            return decrypted, True
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_data, False
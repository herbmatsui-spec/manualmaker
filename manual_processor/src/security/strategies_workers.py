"""
Cloudflare Workers specific security strategies.
These strategies use Cloudflare KV storage and Workers runtime APIs.
"""

import json
import logging
import os
import asyncio
import base64
from typing import List, Tuple, Optional, Any

from .interfaces import PatternProvider, KeyStore, EncryptionProvider
from .strategies import HardcodedPatternProvider

logger = logging.getLogger(__name__)


try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class KVPatternProvider(PatternProvider):
    """Cloudflare KV から PII パターンを読み込むプロバイダー"""

    def __init__(self, kv_binding_name: str = "PII_PATTERNS"):
        """
        Args:
            kv_binding_name: Workers KV namespace binding name
        """
        self.kv_binding_name = kv_binding_name
        self._kv = None

    def _get_kv(self):
        """Get KV namespace from Workers globals"""
        if self._kv is not None:
            return self._kv
        
        # In Cloudflare Workers, KV bindings are available as global variables
        try:
            # Access the binding directly from globals()
            return globals()[self.kv_binding_name]
        except (KeyError, AttributeError):
            # Binding not available (e.g., in local/test environment)
            return None

    def set_kv(self, kv_namespace: Any) -> None:
        """KV namespace を直接設定（テスト用）"""
        self._kv = kv_namespace

    def load_patterns(self) -> List[Tuple[str, str, str]]:
        """KV からパターンを読み込む（取得できない場合はハードコードへフォールバック）"""
        kv = self._get_kv()

        if kv is None:
            logger.warning(f"KV namespace '{self.kv_binding_name}' not available, falling back to hardcoded patterns")
            return HardcodedPatternProvider().load_patterns()

        try:
            # KVからJSONデータを取得
            data = kv.get("pii_patterns", type="json")
            if data is None:
                logger.warning("No patterns found in KV, falling back to hardcoded patterns")
                return HardcodedPatternProvider().load_patterns()

            # JSON 文字列が返された場合はパースする
            if isinstance(data, str):
                data = json.loads(data)

            patterns = []
            # {"patterns": [...]} 形式と [...] 形式の両方に対応
            items = data.get("patterns", []) if isinstance(data, dict) else data
            for item in items:
                if isinstance(item, dict) and item.get("enabled", True):
                    patterns.append((
                        item["name"],
                        item["regex"],
                        item["mask"]
                    ))

            logger.info(f"Loaded {len(patterns)} PII patterns from KV")
            return patterns

        except Exception as e:
            logger.error(f"Failed to load patterns from KV: {e}")
            return HardcodedPatternProvider().load_patterns()


class KVKeyStore(KeyStore):
    """Cloudflare KV を使った API キー保存"""

    def __init__(self, kv_binding_name: str = "API_KEYS"):
        """
        Args:
            kv_binding_name: Workers KV namespace binding name for API keys
        """
        self.kv_binding_name = kv_binding_name
        self._kv = None

    def _get_kv(self):
        """Get KV namespace from Workers globals"""
        if self._kv is not None:
            return self._kv
        
        # In Cloudflare Workers, KV bindings are available as global variables
        try:
            # Access the binding directly from globals()
            return globals()[self.kv_binding_name]
        except (KeyError, AttributeError):
            # Binding not available (e.g., in local/test environment)
            return None

    def set_kv(self, kv_namespace: Any) -> None:
        """KV namespace を直接設定（テスト用）"""
        self._kv = kv_namespace

    def _make_key(self, service: str, username: str) -> str:
        """KV用のキーを生成"""
        return f"{service}:{username}"

    def get(self, service: str, username: str) -> Optional[str]:
        """KV から API キーを取得"""
        kv = self._get_kv()
        if kv is None:
            logger.warning(f"KV namespace '{self.kv_binding_name}' not available")
            return None

        try:
            key = self._make_key(service, username)
            value = kv.get(key, type="text")
            return value
        except Exception as e:
            logger.error(f"Failed to get API key from KV: {e}")
            return None

    def set(self, service: str, username: str, value: str) -> None:
        """KV に API キーを保存"""
        kv = self._get_kv()
        if kv is None:
            logger.warning(f"KV namespace '{self.kv_binding_name}' not available")
            return

        try:
            key = self._make_key(service, username)
            kv.put(key, value)
            logger.info(f"Stored API key for {service}/{username} in KV")
        except Exception as e:
            logger.error(f"Failed to store API key in KV: {e}")
            raise

    def delete(self, service: str, username: str) -> None:
        """KV から API キーを削除"""
        kv = self._get_kv()
        if kv is None:
            return

        try:
            key = self._make_key(service, username)
            kv.delete(key)
            logger.info(f"Deleted API key for {service}/{username} from KV")
        except Exception as e:
            logger.error(f"Failed to delete API key from KV: {e}")
            raise


class WorkersEncryption(EncryptionProvider):
    """Cloudflare Workers encryption using Web Crypto API (SubtleCrypto)"""
    
    def __init__(self, key_binding_name: str = "ENCRYPTION_KEY"):
        """
        Args:
            key_binding_name: Environment variable name containing base64-encoded 32-byte key
        """
        self.key_binding_name = key_binding_name
        self._key = None  # Will be raw bytes key

    def _get_key(self) -> Optional[bytes]:
        """Get and prepare encryption key from environment"""
        if self._key is not None:
            return self._key
        
        key_b64 = os.environ.get(self.key_binding_name)
        if not key_b64:
            return None
            
        try:
            # Decode base64 key
            key_bytes = base64.b64decode(key_b64)
            if len(key_bytes) != 32:
                return None
            self._key = key_bytes
            return self._key
        except Exception:
            return None

    def encrypt(self, data: bytes) -> Tuple[bytes, bool]:
        """Encrypt using Web Crypto API (synchronous version for compatibility)"""
        key = self._get_key()
        if key is None:
            return data, False
            
        try:
            # Access Workers Web Crypto API
            # Note: In actual Workers, this would be async, but we provide a sync wrapper
            # For true Workers deployment, this would need to be async, 
            # but we'll provide a compatibility layer
            from workers import crypto
            
            async def _encrypt():
                # Generate IV
                iv = crypto.getRandomValues(bytearray(12))
                
                # Import key
                crypto_key = await crypto.subtle.import_key(
                    "raw", key, {"name": "AES-GCM"}, False, ["encrypt"]
                )
                
                # Encrypt
                encrypted = await crypto.subtle.encrypt(
                    {"name": "AES-GCM", "iv": iv},
                    crypto_key,
                    data
                )
                return iv + encrypted
            
            # Run async function in sync context (works in Workers via event loop)
            result = asyncio.run(_encrypt())
            return result, True
        except Exception:
            # Fallback: if crypto not available, return unencrypted
            return data, False

    def decrypt(self, encrypted_data: bytes) -> Tuple[bytes, bool]:
        """Decrypt using Web Crypto API"""
        if len(encrypted_data) < 12:
            return encrypted_data, False
            
        key = self._get_key()
        if key is None:
            return encrypted_data, False
            
        try:
            from workers import crypto
            
            async def _decrypt():
                # Extract IV and ciphertext
                iv = encrypted_data[:12]
                ciphertext = encrypted_data[12:]
                
                # Import key
                crypto_key = await crypto.subtle.import_key(
                    "raw", key, {"name": "AES-GCM"}, False, ["decrypt"]
                )
                
                # Decrypt
                decrypted = await crypto.subtle.decrypt(
                    {"name": "AES-GCM", "iv": iv},
                    crypto_key,
                    ciphertext
                )
                return decrypted
            
            result = asyncio.run(_decrypt())
            return result, True
        except Exception:
            return encrypted_data, False


def create_workers_config() -> "SecurityConfig":
    """
    Cloudflare Workers 環境用の SecurityConfig を作成するファクトリ関数。

    環境変数や Workers バインディングから自動的に設定を構築します。
    """
    from .config import SecurityConfig
    from .strategies import HardcodedPatternProvider, EnvVarKeyStore, NoOpEncryption

    # Workers環境では KV バインディングがグローバルに利用可能
    # ここでは遅延初期化されるプロバイダーを作成

    pattern_provider = KVPatternProvider("PII_PATTERNS")
    key_store = KVKeyStore("API_KEYS")

    # 暗号化は環境変数にキーがある場合のみ有効
    encryption_provider = NoOpEncryption()
    if "ENCRYPTION_KEY" in os.environ and _HAS_CRYPTO:
        encryption_provider = WorkersEncryption("ENCRYPTION_KEY")

    return SecurityConfig(
        pattern_provider=pattern_provider,
        key_store=key_store,
        encryption_provider=encryption_provider
    )
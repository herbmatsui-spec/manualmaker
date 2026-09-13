"""
Security configuration for dependency injection.
Allows runtime selection of backend strategies.
"""
from typing import Optional
from .interfaces import PatternProvider, KeyStore, EncryptionProvider
from .strategies import (
    HardcodedPatternProvider,
    EnvVarKeyStore,
    NoOpEncryption,
    FernetEncryption
)

try:
    import yaml
    import keyring
    from cryptography.fernet import Fernet
    _HAS_YAML = True
    _HAS_KEYRING = True
    _HAS_FERNET = True
except ImportError:
    _HAS_YAML = False
    _HAS_KEYRING = False
    _HAS_FERNET = False


class SecurityConfig:
    """Security backend設定を管理するクラス"""
    
    def __init__(
        self,
        pattern_provider: Optional[PatternProvider] = None,
        key_store: Optional[KeyStore] = None,
        encryption_provider: Optional[EncryptionProvider] = None
    ):
        """
        セキュリティバックエンドの戦略を設定
        
        Args:
            pattern_provider: PIIパターンプロバイダー（Noneの場合は自動選択）
            key_store: APIキーストア（Noneの場合は自動選択）
            encryption_provider: 暗号化プロバイダー（Noneの場合は自動選択）
        """
        self.pattern_provider = pattern_provider or self._get_default_pattern_provider()
        self.key_store = key_store or self._get_default_key_store()
        self.encryption_provider = encryption_provider or self._get_default_encryption_provider()
    
    def _get_default_pattern_provider(self) -> PatternProvider:
        """環境に応じたデフォルトパターンプロバイダーを返す"""
        if _HAS_YAML:
            # YAMLファイルがある場合はそれを使う戦略（後で実装）
            # 今はハードコードにフォールバック
            pass
        return HardcodedPatternProvider()
    
    def _get_default_key_store(self) -> KeyStore:
        """環境に応じたデフォルトキーストアを返す"""
        if _HAS_KEYRING:
            # keyringがある場合はそれを使う戦略（後で実装）
            # 今は環境変数にフォールバック
            pass
        return EnvVarKeyStore()
    
    def _get_default_encryption_provider(self) -> EncryptionProvider:
        """環境に応じたデフォルト暗号化プロバイダーを返す"""
        if _HAS_FERNET:
            # Fernetが利用可能ならFernetEncryptionを使用
            return FernetEncryption()
        return NoOpEncryption()
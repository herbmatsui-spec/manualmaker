"""
Security configuration for dependency injection.
Allows runtime selection of backend strategies.
"""
from typing import Optional
from .interfaces import PatternProvider, KeyStore, EncryptionProvider
from .strategies_workers import (
    KVPatternProvider,
    KVKeyStore,
    WebCryptoEncryption
)


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
        return KVPatternProvider()
    
    def _get_default_key_store(self) -> KeyStore:
        """環境に応じたデフォルトキーストアを返す"""
        return KVKeyStore()
    
    def _get_default_encryption_provider(self) -> EncryptionProvider:
        """環境に応じたデフォルト暗号化プロバイダーを返す"""
        return WebCryptoEncryption()

    @classmethod
    def from_workers_env(
        cls,
        pattern_kv_binding: str = "PII_PATTERNS",
        key_kv_binding: str = "API_KEYS",
        encryption_key_env: str = "ENCRYPTION_KEY"
    ) -> 'SecurityConfig':
        """
        Cloudflare Workers環境用の設定を作成するファクトリメソッド
        
        Args:
            pattern_kv_binding: PIIパターンを格納するKV namespace binding名
            key_kv_binding: APIキーを格納するKV namespace binding名
            encryption_key_env: 暗号化キーを格納する環境変数名
            
        Returns:
            Workers環境に最適化されたSecurityConfigインスタンス
        """
        return cls(
            pattern_provider=KVPatternProvider(pattern_kv_binding),
            key_store=KVKeyStore(key_kv_binding),
            encryption_provider=WebCryptoEncryption(encryption_key_env)
        )
# Plan 2: Strategy Pattern Implementation - Phase 3
## Cloudflare Workers対応戦略フェーズ

### フェーズ目標
Cloudflare Workers環境で動作する戦略クラスを実装する。
KVストレージを使ったパターン提供、APIキー保存、およびWeb Crypto APIを使った暗号化を実装する。
このフェーズではWorkers固依存性を策定し、ローカル開発環境との差異を吸収する。

### ステップ 1: KVパターンプロバイダーの実装
- ファイル: `src/security/strategies_workers.py` を新規作成（Workers専用ファイルとして分離）
- 内容:
```python
"""
Cloudflare Workers専用セキュリティバックエンド戦略
KVストレージとWeb Crypto APIを使用
"""
import json
import logging
from typing import List, Tuple, Optional
from .interfaces import PatternProvider, KeyStore, EncryptionProvider, MaskedPosition

logger = logging.getLogger(__name__)


class KVPatternProvider(PatternProvider):
    """Cloudflare KVからPIIパターンを読み込むプロバイダー"""
    
    def __init__(self, kv_namespace_binding: str = "PII_PATTERNS"):
        """
        KVパターンプロバイダーを初期化
        
        Args:
            kv_namespace_binding: wrangler.tomlで定義されたKV namespace binding名
        """
        self.kv_namespace_binding = kv_namespace_binding
        self._kv = None  # lazy initialization
    
    @property
    def kv(self):
        """KV namespaceバインディングを取得（遅延初期化）"""
        if self._kv is None:
            # Workers環境ではグローバルスコープでバインディングが利用可能
            # ローカル開発時はwranglerが提供するモックを使用
            try:
                self._kv = __import__('workers').WorkersEnv[self.kv_namespace_binding]
            except (ImportError, AttributeError, KeyError):
                # ローカルテストや開発環境ではNoneを返す
                # テストではモックを注入するか、環境変数でフォールバックさせる
                self._kv = None
        return self._kv
    
    def load_patterns(self) -> List[Tuple[str, str, str]]:
        """KVからPIIパターンJSONを読み込み、パターンリストに変換"""
        if self.kv is None:
            # KVが利用できない場合はハードコードデフォルトにフォールバック
            logger.warning("KV namespace not available, falling back to hardcoded patterns")
            from .strategies import HardcodedPatternProvider
            return HardcodedPatternProvider().load_patterns()
        
        try:
            # KVからJSON文字列を取得
            patterns_json = self.kv.get("patterns", type="text")
            if not patterns_json:
                logger.warning("No patterns found in KV, using hardcoded defaults")
                from .strategies import HardcodedPatternProvider
                return HardcodedPatternProvider().load_patterns()
            
            # JSONをパースしてパターンリストに変換
            patterns_data = json.loads(patterns_json)
            patterns = []
            for item in patterns_data:
                if item.get("enabled", True):
                    patterns.append((
                        item["name"],
                        item["regex"],
                        item["mask"]
                    ))
            
            logger.info(f"Loaded {len(patterns)} patterns from KV")
            return patterns if patterns else HardcodedPatternProvider().load_patterns()
            
        except Exception as e:
            logger.error(f"Failed to load patterns from KV: {e}")
            from .strategies import HardcodedPatternProvider
            return HardcodedPatternProvider().load_patterns()
```

### ステップ 2: KVキーストラテジーの実装
- ファイル: `src/security/strategies_workers.py` を編集
- 追加内容 (ファイル末尾に):
```python
class KVKeyStore(KeyStore):
    """Cloudflare KVを使ったAPIキー保存ストレージ"""
    
    def __init__(self, kv_namespace_binding: str = "API_KEYS"):
        """
        KVキーストアを初期化
        
        Args:
            kv_namespace_binding: wrangler.tomlで定義されたKV namespace binding名
        """
        self.kv_namespace_binding = kv_namespace_binding
        self._kv = None
    
    @property
    def kv(self):
        """KV namespaceバインディングを取得（遅延初期化）"""
        if self._kv is None:
            try:
                self._kv = __import__('workers').WorkersEnv[self.kv_namespace_binding]
            except (ImportError, AttributeError, KeyError):
                self._kv = None
        return self._kv
    
    def get(self, service: str, username: str) -> Optional[str]:
        """KVからAPIキーを取得"""
        if self.kv is None:
            logger.warning("KV namespace not available for key retrieval")
            return None
        
        key = f"{service}:{username}"
        try:
            value = self.kv.get(key, type="text")
            return value
        except Exception as e:
            logger.error(f"Failed to get key {key} from KV: {e}")
            return None
    
    def set(self, service: str, username: str, value: str) -> None:
        """KVにAPIキーを保存"""
        if self.kv is None:
            logger.warning("KV namespace not available for key storage")
            return
        
        key = f"{service}:{username}"
        try:
            self.kv.put(key, value)
            logger.info(f"Stored API key for {service}/{username} in KV")
        except Exception as e:
            logger.error(f"Failed to set key {key} in KV: {e}")
            raise
    
    def delete(self, service: str, username: str) -> None:
        """KVからAPIキーを削除"""
        if self.kv is None:
            logger.warning("KV namespace not available for key deletion")
            return
        
        key = f"{service}:{username}"
        try:
            self.kv.delete(key)
            logger.info(f"Deleted API key for {service}/{username} from KV")
        except Exception as e:
            logger.error(f"Failed to delete key {key} from KV: {e}")
            raise
```

### ステップ 3: Web Crypto暗号化ストラテジーの実装
- ファイル: `src/security/strategies_workers.py` を編集
- 追加内容 (ファイル末尾に):
```python
class WebCryptoEncryption(EncryptionProvider):
    """Cloudflare WorkersのWeb Crypto API (SubtleCrypto) を使った暗号化"""
    
    def __init__(self, key_env_var: str = "ENCRYPTION_KEY"):
        """
        Web Crypto暗号化を初期化
        
        Args:
            key_env_var: 暗号化キーを格納する環境変数名（WorkersではSecretsから設定）
        """
        self.key_env_var = key_env_var
        self._key = None  # 暗号化キー（遅延取得）
    
    def _get_key(self) -> Optional[bytes]:
        """環境変数から暗号化キーを取得し、32バイトに調整"""
        if self._key is not None:
            return self._key
        
        import os
        key_str = os.environ.get(self.key_env_var, "")
        if not key_str:
            logger.warning(f"Encryption key not found in environment variable {self.key_env_var}")
            return None
        
        try:
            # keyが32バイト未満の場合はパディング、超える場合は truncate
            key_bytes = key_str.encode('utf-8')
            if len(key_bytes) < 32:
                key_bytes = key_bytes.ljust(32, b'\0')[:32]
            else:
                key_bytes = key_bytes[:32]
            
            self._key = key_bytes
            return self._key
        except Exception as e:
            logger.error(f"Failed to process encryption key: {e}")
            return None
    
    async def encrypt(self, data: bytes) -> Tuple[bytes, bool]:
        """Web Crypto APIを使ってデータをAES-GCMで暗号化"""
        key = self._get_key()
        if key is None:
            logger.warning("Encryption key not available")
            return data, False
        
        try:
            # Workers環境ではグローバルのcryptoオブジェクトが利用可能
            # ローカル開発時はポリフィルまたはモックが必要
            try:
                from workers import crypto
            except ImportError:
                # ローカルテスト環境 - 簡易実装またはエラー
                logger.warning("Web Crypto API not available in local environment")
                return data, False
            
            # IV（初期化ベクトル）を生成 - 12バイト推奨
            iv = crypto.getRandomValues(new Uint8Array(12))
            
            # キーをインポート
            crypto_key = await crypto.subtle.import_key(
                "raw",
                key,
                {"name": "AES-GCM"},
                False,
                ["encrypt"]
            )
            
            # 暗号化実行
            encrypted_buffer = await crypto.subtle.encrypt(
                {
                    "name": "AES-GCM",
                    "iv": iv
                },
                crypto_key,
                data
            )
            
            # 結果をバイト列に変換し、IVを先頭に結合（復号時に必要）
            encrypted_bytes = bytes(encrypted_buffer)
            return iv + encrypted_bytes, True
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return data, False
    
    async def decrypt(self, encrypted_data: bytes) -> Tuple[bytes, bool]:
        """Web Crypto APIを使ってデータをAES-GCMで復号"""
        if len(encrypted_data) < 12:  # IVサイズ分必要
            logger.warning("Encrypted data too short for IV")
            return encrypted_data, False
        
        key = self._get_key()
        if key is None:
            logger.warning("Encryption key not available")
            return encrypted_data, False
        
        try:
            from workers import crypto
        except ImportError:
            logger.warning("Web Crypto API not available in local environment")
            return encrypted_data, False
        
        try:
            # IVと暗号化データを分離
            iv = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            
            # キーをインポート
            crypto_key = await crypto.subtle.import_key(
                "raw",
                key,
                {"name": "AES-GCM"},
                False,
                ["decrypt"]
            )
            
            # 復号実行
            decrypted_buffer = await crypto.subtle.decrypt(
                {
                    "name": "AES-GCM",
                    "iv": iv
                },
                crypto_key,
                ciphertext
            )
            
            decrypted_bytes = bytes(decrypted_buffer)
            return decrypted_bytes, True
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_data, False
```

### ステップ 4: Workers環境用設定ファクトリの追加
- ファイル: `src/security/config.py` を編集
- 追加内容:
```python
# ファイル冒頭に追加（既存インポートの後）
from .strategies_workers import (
    KVPatternProvider,
    KVKeyStore,
    WebCryptoEncryption
)

# SecurityConfigクラス内にメソッドを追加
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
```

### フェーズ完了条件
- `src/security/strategies_workers.py` が存在し、3つのWorkers専用戦略クラスが実装されている
- `src/security/config.py` に `from_workers_env` ファクトリメソッドが追加されている
- 既存のローカル環境での動作は変更されていない
- 注意点: このフェーズのコードはWorkers環境でのみ完全に動作する。ローカル開発・テストではモックやフォールバックが必要になる。

---
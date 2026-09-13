# Plan 2: Strategy Pattern Implementation - Phase 2
## 既存バックエンドの戦略化フェーズ

### フェーズ目標
フェーズ1で定義したインターフェースを使って、既存のYAML/file system、keyring、cryptography.fernet実装を戦略クラスとして実装する。
このフェーズでは依存性注入の仕組みを作り、SecurityManagerを後方互換性を保ちながらリファクタリングする準備をする。

### ステップ 1: 戦略実装ファイルの作成とハードコード戦略の実装
- ファイル: `src/security/strategies.py` を新規作成
- 内容:
```python
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
```

### ステップ 2: 環境変数キーストラテジーの実装
- ファイル: `src/security/strategies.py` を編集
- 追加内容 (ファイル末尾に):
```python
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
```

### ステップ 3: 暗号化無効戦略の実装
- ファイル: `src/security/strategies.py` を編集
- 追加内容 (ファイル末尾に):
```python
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
```

### ステップ 4: 設定クラスの作成
- ファイル: `src/security/config.py` を新規作成
- 内容:
```python
"""
Security configuration for dependency injection.
Allows runtime selection of backend strategies.
"""
from typing import Optional
from .interfaces import PatternProvider, KeyStore, EncryptionProvider
from .strategies import (
    HardcodedPatternProvider,
    EnvVarKeyStore,
    NoOpEncryption
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
            # 暗号化ライブラリがある場合はそれを使う戦略（後で実装）
            # 今は無効にフォールバック
            pass
        return NoOpEncryption()
```

### ステップ 5: SecurityManagerへの設定注入準備（後方互換維持）
- ファイル: `src/security_manager.py` を編集
- 変更点:
  1. ファイル冒頭にインポートを追加
  2. クラスメソッドにオプショナルな`config`パラメータを追加
  3. 内部ロジックを変更して、configが提供されればそれを使い、なければ既存の動作を維持

```diff
@@
-from src.security_manager import SecurityManager
+from src.security_manager import SecurityManager, SecurityConfig
+
+
+def test_security_manager_with_config():
+    """SecurityManagerがSecurityConfigを受け取れることをテスト"""
+    config = SecurityConfig()
+    # 現在はデフォルト戦略を使うので通常通り動作するはず
+    masked, info = SecurityManager.mask_sensitive_data("test@example.com", config=config)
+    assert "[REDACTED_EMAIL]" in masked
```

実際のSecurityManagerの変更は次ステップで行うが、まずはテストを追加して方向性を確認する。

### フェーズ完了条件
- `src/security/strategies.py` が存在し、3つの具体的戦略クラスが実装されている
- `src/security/config.py` が存在し、SecurityConfigクラスが実装されている
- 既存のSecurityManagerの動作は変更されていない（後方互換性）
- 新しいテストがパスするか、またはテストが書かれている（実際の変更は次フェーズ）

---
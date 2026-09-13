# Plan 2: Strategy Pattern Implementation - Phase 1
## インターフェース定義フェーズ

### フェーズ目標
SecurityManager の外部依存を抽象化するためのインターフェース(Protocol)を定義する。
このフェーズでは依存性注入の基盤を作り、既存動作を変更しない。

### ステップ 1: PatternProvider Protocol の作成
- ファイル: `src/security/interfaces.py` を新規作成
- 内容:
```python
"""
Security backend interfaces for dependency injection.
Defines protocols that can be implemented by different backends.
"""
from typing import Protocol, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class MaskedPosition:
    """Position of masked data in text"""
    start: int
    end: int
    mask_type: str
    original_length: int


class PatternProvider(Protocol):
    """PIIパターンを提供するインターフェース"""
    
    def load_patterns(self) -> List[Tuple[str, str, str]]:
        """
        PIIパターンのリストを返す
        
        Returns:
            List of tuples: (pattern_name, regex, mask)
        """
        ...
```

### ステップ 2: KeyStore Protocol の追加
- ファイル: `src/security/interfaces.py` を編集
- 追加内容 (ファイル末尾に):
```python
class KeyStore(Protocol):
    """APIキー保存ストレージのインターフェース"""
    
    def get(self, service: str, username: str) -> Optional[str]:
        """
        APIキーを取得
        
        Args:
            service: サービス名 (例: "gemini")
            username: ユーザー名 (例: "api_key")
            
        Returns:
            APIキー文字列、見つからない場合はNone
        """
        ...
    
    def set(self, service: str, username: str, value: str) -> None:
        """
        APIキーを保存
        
        Args:
            service: サービス名
            username: ユーザー名
            value: 保存するAPIキー値
        """
        ...
    
    def delete(self, service: str, username: str) -> None:
        """
        APIキーを削除
        
        Args:
            service: サービス名
            username: ユーザー名
        """
        ...
```

### ステップ 3: EncryptionProvider Protocol の追加
- ファイル: `src/security/interfaces.py` を編集
- 追加内容 (ファイル末尾に):
```python
class EncryptionProvider(Protocol):
    """データ暗号化を提供するインターフェース"""
    
    def encrypt(self, data: bytes) -> Tuple[bytes, bool]:
        """
        データを暗号化
        
        Args:
            data: 暗号化するバイトデータ
            
        Returns:
            (encrypted_data, success) のタプル
        """
        ...
    
    def decrypt(self, encrypted_data: bytes) -> Tuple[bytes, bool]:
        """
        データを復号
        
        Args:
            encrypted_data: 暗号化されたバイトデータ
            
        Returns:
            (decrypted_data, success) のタプル
        """
        ...
```

### ステップ 4: 基本テストの作成
- ファイル: `tests/test_security_interfaces.py` を新規作成
- 内容:
```python
"""
Tests for security backend interfaces
"""
import pytest
from src.security.interfaces import PatternProvider, KeyStore, EncryptionProvider, MaskedPosition


def test_pattern_provider_protocol():
    """PatternProvider プロトコルの基本構造をテスト"""
    # プロトコルなのでインスタンス化はできないが、サブクラスで実装必須であることを確認
    assert hasattr(PatternProvider, 'load_patterns')
    
    
def test_key_store_protocol():
    """KeyStore プロトコルの基本構造をテスト"""
    assert hasattr(KeyStore, 'get')
    assert hasattr(KeyStore, 'set')
    assert hasattr(KeyStore, 'delete')
    
    
def test_encryption_provider_protocol():
    """EncryptionProvider プロトコルの基本構造をテスト"""
    assert hasattr(EncryptionProvider, 'encrypt')
    assert hasattr(EncryptionProvider, 'decrypt')
    
    
def test_masked_position_dataclass():
    """MaskedPosition データクラスの動作をテスト"""
    pos = MaskedPosition(start=0, end=5, mask_type="TEST", original_length=5)
    assert pos.start == 0
    assert pos.end == 5
    assert pos.mask_type == "TEST"
    assert pos.original_length == 5
```

### フェーズ完了条件
- `src/security/interfaces.py` が存在し、3つのProtocolが定義されている
- `tests/test_security_interfaces.py` がすべてパスする
- 既存のコードは変更不要（後方互換性維持）

---
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
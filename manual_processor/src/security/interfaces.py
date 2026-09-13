"""
Abstract interfaces for security backend strategies.
Defines the contracts implemented by strategies.py and consumed by config.py.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class MaskedPosition:
    """Position of masked data in text"""
    start: int
    end: int
    mask_type: str
    original_length: int


class PatternProvider(ABC):
    """PIIパターンを提供するインターフェース"""

    @abstractmethod
    def load_patterns(self) -> List[Tuple[str, str, str]]:
        """(name, pattern, replacement) のタプルリストを返す"""
        raise NotImplementedError


class KeyStore(ABC):
    """APIキーストアのインターフェース"""

    @abstractmethod
    def get(self, service: str, username: str) -> Optional[str]:
        """APIキーを取得する。見つからない場合は None を返す"""
        raise NotImplementedError

    @abstractmethod
    def set(self, service: str, username: str, value: str) -> None:
        """APIキーを保存する"""
        raise NotImplementedError

    @abstractmethod
    def delete(self, service: str, username: str) -> None:
        """APIキーを削除する"""
        raise NotImplementedError


class EncryptionProvider(ABC):
    """暗号化プロバイダーのインターフェース"""

    @abstractmethod
    def encrypt(self, data: bytes) -> Tuple[bytes, bool]:
        """データを暗号化する。戻り値は (変換後データ, 暗号化したか否か)"""
        raise NotImplementedError

    @abstractmethod
    def decrypt(self, encrypted_data: bytes) -> Tuple[bytes, bool]:
        """データを復号する。戻り値は (変換後データ, 復号したか否か)"""
        raise NotImplementedError

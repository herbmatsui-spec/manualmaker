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
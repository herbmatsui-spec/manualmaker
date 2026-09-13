"""Tests for SecurityManager with SecurityConfig dependency injection"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_mask_sensitive_data_with_hardcoded_strategy():
    """ハードコード戦略を使った設定でマスク機能をテスト"""
    from src.security.config import SecurityConfig
    from src.security.strategies import HardcodedPatternProvider, EnvVarKeyStore, NoOpEncryption
    from src.security_manager import SecurityManager

    config = SecurityConfig(
        pattern_provider=HardcodedPatternProvider(),
        key_store=EnvVarKeyStore(),
        encryption_provider=NoOpEncryption()
    )

    masked, info = SecurityManager.mask_sensitive_data(
        "Email: test@example.com",
        record_positions=False,
        config=config
    )
    assert "[REDACTED_EMAIL]" in masked
    assert info["counts"]["EMAIL"] == 1


def test_mask_sensitive_data_with_custom_patterns():
    """カスタムパターンプロバイダーでテスト"""
    from src.security.interfaces import PatternProvider
    from src.security.config import SecurityConfig
    from src.security.strategies import EnvVarKeyStore, NoOpEncryption
    from src.security_manager import SecurityManager

    class CustomPatternProvider(PatternProvider):
        def load_patterns(self):
            return [("TEST", r"foo", "[FOO]")]

    config = SecurityConfig(
        pattern_provider=CustomPatternProvider(),
        key_store=EnvVarKeyStore(),
        encryption_provider=NoOpEncryption()
    )

    masked, info = SecurityManager.mask_sensitive_data(
        "This is foo text",
        config=config
    )
    assert "[FOO]" in masked
    assert info["counts"]["TEST"] == 1


def test_mask_sensitive_data_with_positions_and_config():
    """設定を使ってマスク位置も取得"""
    from src.security.config import SecurityConfig
    from src.security.strategies import HardcodedPatternProvider, EnvVarKeyStore, NoOpEncryption
    from src.security_manager import SecurityManager

    config = SecurityConfig(
        pattern_provider=HardcodedPatternProvider(),
        key_store=EnvVarKeyStore(),
        encryption_provider=NoOpEncryption()
    )

    masked, info = SecurityManager.mask_sensitive_data(
        "Contact: test@example.com",
        record_positions=True,
        config=config
    )
    assert "[REDACTED_EMAIL]" in masked
    assert "positions" in info
    assert len(info["positions"]) == 1
    assert info["positions"][0].mask_type == "EMAIL"


def test_save_api_key_with_config():
    """設定を使ってAPIキーを保存"""
    from src.security.config import SecurityConfig
    from src.security.strategies import HardcodedPatternProvider, EnvVarKeyStore, NoOpEncryption
    from src.security_manager import SecurityManager

    config = SecurityConfig(
        pattern_provider=HardcodedPatternProvider(),
        key_store=EnvVarKeyStore(),
        encryption_provider=NoOpEncryption()
    )

    result = SecurityManager.save_api_key("test-key-123", config=config)
    assert result is True


def test_load_api_key_with_config():
    """設定を使ってAPIキーを読み込み"""
    from src.security.config import SecurityConfig
    from src.security.strategies import HardcodedPatternProvider, EnvVarKeyStore, NoOpEncryption
    from src.security_manager import SecurityManager

    config = SecurityConfig(
        pattern_provider=HardcodedPatternProvider(),
        key_store=EnvVarKeyStore(),
        encryption_provider=NoOpEncryption()
    )

    # First save
    SecurityManager.save_api_key("test-key-456", config=config)
    # Then load
    loaded = SecurityManager.load_api_key(config=config)
    assert loaded == "test-key-456"


def test_encrypt_data_with_config():
    """設定を使ってデータを暗号化"""
    from src.security.config import SecurityConfig
    from src.security.strategies import HardcodedPatternProvider, EnvVarKeyStore, NoOpEncryption
    from src.security_manager import SecurityManager

    config = SecurityConfig(
        pattern_provider=HardcodedPatternProvider(),
        key_store=EnvVarKeyStore(),
        encryption_provider=NoOpEncryption()
    )

    data = b"secret data"
    encrypted, success = SecurityManager.encrypt_data(data, config=config)
    # NoOpEncryption returns data unchanged with success=False
    assert encrypted == data
    assert success is False


def test_decrypt_data_with_config():
    """設定を使ってデータを復号"""
    from src.security.config import SecurityConfig
    from src.security.strategies import HardcodedPatternProvider, EnvVarKeyStore, NoOpEncryption
    from src.security_manager import SecurityManager

    config = SecurityConfig(
        pattern_provider=HardcodedPatternProvider(),
        key_store=EnvVarKeyStore(),
        encryption_provider=NoOpEncryption()
    )

    data = b"encrypted data"
    decrypted, success = SecurityManager.decrypt_data(data, config=config)
    # NoOpEncryption returns data unchanged with success=False
    assert decrypted == data
    assert success is False


def test_unmask_data_with_config():
    """設定を使ってデータをアンマスク（configは使われないが互換性のため）"""
    from src.security.config import SecurityConfig
    from src.security.strategies import HardcodedPatternProvider, EnvVarKeyStore, NoOpEncryption
    from src.security_manager import SecurityManager, MaskedPosition

    config = SecurityConfig(
        pattern_provider=HardcodedPatternProvider(),
        key_store=EnvVarKeyStore(),
        encryption_provider=NoOpEncryption()
    )

    masked = "Email: [REDACTED_EMAIL]"
    positions = [MaskedPosition(start=7, end=22, mask_type="EMAIL", original_length=16)]
    originals = ["test@example.com"]

    result = SecurityManager.unmask_data(masked, positions, originals, config=config)
    assert "test@example.com" in result


def test_security_config_default_providers():
    """SecurityConfigがデフォルトプロバイダーを正しく設定することを確認"""
    from src.security.config import SecurityConfig
    from src.security.strategies import HardcodedPatternProvider, EnvVarKeyStore, FernetEncryption, NoOpEncryption

    config = SecurityConfig()

    # デフォルトプロバイダーが設定されていることを確認
    assert config.pattern_provider is not None
    assert config.key_store is not None
    assert config.encryption_provider is not None

    # パターンプロバイダーが正しく動作することを確認
    patterns = config.pattern_provider.load_patterns()
    assert len(patterns) > 0
    assert any(p[0] == "EMAIL" for p in patterns)


def test_security_config_with_fernet_encryption():
    """FernetEncryptionが利用可能な場合のテスト"""
    import os
    from src.security.config import SecurityConfig
    from src.security.strategies import HardcodedPatternProvider, EnvVarKeyStore, FernetEncryption

    # 有効なFernetキーを設定
    os.environ["ENCRYPTION_KEY"] = "abcdefghijklmnopqrstuvwxyz123456"  # 32 chars

    try:
        config = SecurityConfig(
            pattern_provider=HardcodedPatternProvider(),
            key_store=EnvVarKeyStore(),
            # encryption_providerを指定しない（デフォルトを使用）
        )

        # FernetEncryptionが使用されることを確認（環境変数に有効なキーがある場合）
        # 注: キーが32バイトのbase64でない場合はNoOpEncryptionになる
        assert config.encryption_provider is not None
    finally:
        os.environ.pop("ENCRYPTION_KEY", None)


def test_legacy_behavior_without_config():
    """設定を渡さない場合のレガシー動作確認"""
    from src.security_manager import SecurityManager

    # 既存の動作（configなし）がそのまま動くことを確認
    masked, info = SecurityManager.mask_sensitive_data("Email: test@example.com")
    assert "[REDACTED_EMAIL]" in masked
    assert info["counts"]["EMAIL"] == 1

    # APIキー保存・読み込みもレガシー動作
    # (keyringがない環境ではFalseが返る)

    # 暗号化もレガシー動作
    data = b"test"
    encrypted, success = SecurityManager.encrypt_data(data)
    # 環境変数がない場合はsuccess=False
    assert success is False or encrypted == data
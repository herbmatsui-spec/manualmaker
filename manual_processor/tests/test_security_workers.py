"""
Tests for Cloudflare Workers compatibility
"""
import os
import sys
from unittest.mock import MagicMock, patch
from src.security.strategies_workers import KVPatternProvider, KVKeyStore, WorkersEncryption
from src.security.config import SecurityConfig
from src.security_manager import SecurityManager

def test_kv_pattern_provider_loads_from_kv():
    """Test that KVPatternProvider reads from KV when available"""
    # Mock KV namespace
    mock_kv = MagicMock()
    # Configure the get method to return the PARSED JSON object (not the JSON string)
    # when called with "pii_patterns" and type="json"
    # The KV should store an object with a "patterns" key containing the array
    mock_kv.get.return_value = {"patterns": [{"name": "EMAIL", "regex": "\\S+@\\S+\\.\\S+", "mask": "[REDACTED]", "enabled": True}]}
    
    # Check what module the class is from
    print(f"KVPatternProvider module: {KVPatternProvider.__module__}")
    
    # Set the global variable directly in the module that the class is from
    import importlib
    workers_mod = importlib.import_module(KVPatternProvider.__module__)
    original_value = getattr(workers_mod, "PII_PATTERNS", None)
    setattr(workers_mod, "PII_PATTERNS", mock_kv)
    
    try:
        # Verify that the global was set correctly
        assert getattr(workers_mod, "PII_PATTERNS") is mock_kv
        
        provider = KVPatternProvider("PII_PATTERNS")
        
        # Test what the mock returns when called with the specific arguments
        test_result = mock_kv.get("pii_patterns", type="json")
        assert test_result == {"patterns": [{"name": "EMAIL", "regex": "\\S+@\\S+\\.\\S+", "mask": "[REDACTED]", "enabled": True}]}
        
        patterns = provider.load_patterns()
        
        assert len(patterns) == 1
        assert patterns[0][0] == "EMAIL"
        assert "[REDACTED]" in patterns[0][2]
    finally:
        # Restore original value
        if original_value is None:
            delattr(workers_mod, "PII_PATTERNS")
        else:
            setattr(workers_mod, "PII_PATTERNS", original_value)

def test_kv_pattern_provider_fallback_when_kv_unavailable():
    """Test that KVPatternProvider falls back when KV is not available"""
    # Ensure the global variable is not set or is None
    import src.security.strategies_workers as workers_mod
    original_value = getattr(workers_mod, "PII_PATTERNS", None)
    if hasattr(workers_mod, "PII_PATTERNS"):
        delattr(workers_mod, "PII_PATTERNS")
    
    try:
        # Verify that the global was removed
        assert not hasattr(workers_mod, "PII_PATTERNS")
        
        provider = KVPatternProvider("PII_PATTERNS")
        patterns = provider.load_patterns()
        
        # Should fall back to hardcoded patterns
        assert len(patterns) > 0
        # Check that we got some expected patterns
        pattern_names = [p[0] for p in patterns]
        assert "EMAIL" in pattern_names
    finally:
        # Restore original value
        if original_value is None:
            if hasattr(workers_mod, "PII_PATTERNS"):
                delattr(workers_mod, "PII_PATTERNS")
        else:
            setattr(workers_mod, "PII_PATTERNS", original_value)


def test_kv_key_store_get_set():
    """Test KVKeyStore basic operations"""
    # Mock KV namespace
    mock_kv = MagicMock()
    mock_kv.get.return_value = "test-value"
    
    # Set the global variable for API_KEYS
    import src.security.strategies_workers as workers_mod
    original_value = getattr(workers_mod, "API_KEYS", None)
    setattr(workers_mod, "API_KEYS", mock_kv)
    
    try:
        store = KVKeyStore("API_KEYS")
        
        # Test get
        value = store.get("gemini", "api_key")
        assert value == "test-value"
        mock_kv.get.assert_called_with("gemini:api_key", type="text")
        
        # Test set
        store.set("gemini", "api_key", "new-value")
        mock_kv.put.assert_called_with("gemini:api_key", "new-value")
        
        # Test delete
        store.delete("gemini", "api_key")
        mock_kv.delete.assert_called_with("gemini:api_key")
    finally:
        # Restore original value
        if original_value is None:
            delattr(workers_mod, "API_KEYS")
        else:
            setattr(workers_mod, "API_KEYS", original_value)

def test_kv_key_store_get_missing():
    """Test KVKeyStore get returns None for missing key"""
    # Mock KV namespace returning None
    mock_kv = MagicMock()
    mock_kv.get.return_value = None
    
    import src.security.strategies_workers as workers_mod
    original_value = getattr(workers_mod, "API_KEYS", None)
    setattr(workers_mod, "API_KEYS", mock_kv)
    
    try:
        store = KVKeyStore("API_KEYS")
        value = store.get("gemini", "api_key")
        assert value is None
        mock_kv.get.assert_called_with("gemini:api_key", type="text")
    finally:
        if original_value is None:
            delattr(workers_mod, "API_KEYS")
        else:
            setattr(workers_mod, "API_KEYS", original_value)


def test_workers_encryption_no_key():
    """Test WorkersEncryption returns original data when no key available"""
    provider = WorkersEncryption("ENCRYPTION_KEY")
    # Ensure no env var set
    with patch.dict('os.environ', {}, clear=True):
        data = b"test data"
        encrypted, success = provider.encrypt(data)
        assert success is False
        assert encrypted == data
        
        decrypted, success = provider.decrypt(data)
        assert success is False
        assert decrypted == data

def test_workers_encryption_with_key_mock():
    """Test WorkersEncryption encrypt/decrypt with mocked crypto"""
    # Create a test key (32 bytes)
    import base64
    import os
    test_key = os.urandom(32)
    key_b64 = base64.b64encode(test_key).decode()
    
    # Mock the workers module and its crypto.subtle
    class MockSubtle:
        async def import_key(self, fmt, key, alg, extractable, usages):
            # Return a mock key object
            return MockKey()
        
        async def encrypt(self, params, key, data):
            # Return mock encrypted data (just prepend "enc:")
            return b"enc:" + data
        
        async def decrypt(self, params, key, data):
            # Assume data starts with "enc:" and strip it
            if data.startswith(b"enc:"):
                return data[4:]
            return data
    
    class MockKey:
        pass
    
    class MockCrypto:
        subtle = MockSubtle()
        
        def getRandomValues(self, arr):
            # Fill with deterministic bytes for testing
            for i in range(len(arr)):
                arr[i] = i % 256
            return arr
    
    # Insert the mock workers module into sys.modules
    sys.modules['workers'] = MockCrypto()
    try:
        with patch.dict('os.environ', {"ENCRYPTION_KEY": key_b64}):
            provider = WorkersEncryption("ENCRYPTION_KEY")
            
            # Test encryption
            plaintext = b"hello world"
            encrypted, success = provider.encrypt(plaintext)
            print(f"DEBUG: encrypt success={success}, encrypted={encrypted}")
            if not success:
                # Try to see what exception occurred by not catching it
                # Temporarily remove try-except? Not possible.
                pass
            assert success is True
            assert encrypted != plaintext
            # Should start with IV (12 bytes) + encrypted data
            assert len(encrypted) > len(plaintext)
            
            # Test decryption
            decrypted, success = provider.decrypt(encrypted)
            print(f"DEBUG: decrypt success={success}, decrypted={decrypted}")
            assert success is True
            assert decrypted == plaintext
    finally:
        # Remove the mock module
        if 'workers' in sys.modules:
            del sys.modules['workers']

def test_workers_encryption_invalid_key():
    """Test WorkersEncryption with invalid key length"""
    # Set a key that is not 32 bytes after decoding
    with patch.dict('os.environ', {"ENCRYPTION_KEY": "YWJj"}):  # "abc" base64 -> 3 bytes
        provider = WorkersEncryption("ENCRYPTION_KEY")
        data = b"test"
        encrypted, success = provider.encrypt(data)
        assert success is False
        assert encrypted == data
        
        decrypted, success = provider.decrypt(data)
        assert success is False
        assert decrypted == data

def test_security_manager_with_workers_config():
    """Test SecurityManager with a config using Workers strategies (mocked)"""
    # Create mock strategies
    mock_pattern = MagicMock()
    mock_pattern.load_patterns.return_value = [
        ("EMAIL", "test@test\\.com", "[REDACTED]")
    ]
    mock_key = MagicMock()
    mock_key.get.return_value = "test-api-key"
    mock_enc = MagicMock()
    mock_enc.encrypt.return_value = (b"encrypted", True)
    mock_enc.decrypt.return_value = (b"decrypted", True)
    
    # Create config with mocks
    config = SecurityConfig(
        pattern_provider=mock_pattern,
        key_store=mock_key,
        encryption_provider=mock_enc
    )
    
    # Test masking
    masked, info = SecurityManager.mask_sensitive_data(
        "Email: test@test.com", config=config
    )
    assert "[REDACTED]" in masked
    mock_pattern.load_patterns.assert_called_once()
    
    # Test API key save
    result = SecurityManager.save_api_key("new-key", config=config)
    assert result is True
    mock_key.set.assert_called_with(
        SecurityManager.SERVICE_NAME, 
        SecurityManager.API_KEY_USERNAME, 
        "new-key"
    )
    
    # Test API key load
    loaded = SecurityManager.load_api_key(config=config)
    assert loaded == "test-api-key"
    mock_key.get.assert_called_with(
        SecurityManager.SERVICE_NAME, 
        SecurityManager.API_KEY_USERNAME
    )
    
    # Test encryption
    encrypted, success = SecurityManager.encrypt_data(b"data", config=config)
    assert success is True
    assert encrypted == b"encrypted"
    mock_enc.encrypt.assert_called_with(b"data")
    
    # Test decryption
    decrypted, success = SecurityManager.decrypt_data(b"encrypted", config=config)
    assert success is True
    assert decrypted == b"decrypted"
    mock_enc.decrypt.assert_called_with(b"encrypted")

def test_create_workers_config_returns_correct_types():
    """Test that create_workers_config returns appropriate strategy instances"""
    from src.security.strategies_workers import create_workers_config
    
    # Test default (no encryption key) -> NoOpEncryption
    with patch.dict('os.environ', {}, clear=True):
        config = create_workers_config()
        assert isinstance(config.pattern_provider, KVPatternProvider)
        assert isinstance(config.key_store, KVKeyStore)
        from src.security.strategies import NoOpEncryption
        assert isinstance(config.encryption_provider, NoOpEncryption)
    
    # Test with encryption key and crypto available -> WorkersEncryption
    # We need to ensure _HAS_CRYPTO is True (it is in our env)
    import base64
    import os
    test_key = os.urandom(32)
    key_b64 = base64.b64encode(test_key).decode()
    with patch.dict('os.environ', {"ENCRYPTION_KEY": key_b64}):
        config = create_workers_config()
        assert isinstance(config.pattern_provider, KVPatternProvider)
        assert isinstance(config.key_store, KVKeyStore)
        assert isinstance(config.encryption_provider, WorkersEncryption)
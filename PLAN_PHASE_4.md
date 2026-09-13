# Plan 2: Strategy Pattern Implementation - Phase 4
## 統合・テスト・後方互換性フェーズ

### フェーズ目標
フェーズ1-3で作成したコンポーネントを統合し、SecurityManagerを実際にリファクタリングする。
後方互換性を完全に保ちながら、新しい設定駆動アーキテクチャを有効にする。
包括的なテストを追加し、ローカル環境とCloudflare Workers環境の両方で動作を確認する。

### ステップ 1: SecurityManagerへの設定注入の実装（コアリファクタリング）
- ファイル: `src/security_manager.py` を編集
- 変更点: 全てのクラスメソッドに`config: Optional[SecurityConfig] = None`パラメータを追加し、提供されればそれを使い、なければ既存の動作を維持するように変更

具体的な変更例（`mask_sensitive_data` メソッド）：
```diff
@@
     @classmethod
     def mask_sensitive_data(cls, text: str, record_positions: bool = False) -> Tuple[str, Dict[str, Any]]:
+        """
+        Mask sensitive personal information in text
+
+        Args:
+            text: Input text to mask
+            record_positions: If True, also return positions of masked items
+            config: Optional SecurityConfig for dependency injection (backward compatible)
+        """
+
+        # Backward compatibility: if no config provided, use legacy behavior
+        if 'config' in locals() and config is not None:
+            # Use provided config
+            patterns = config.pattern_provider.load_patterns()
+        else:
+            # Legacy behavior - existing code
+            patterns = cls._load_pii_patterns()
+
         masked = text
         counts = {}
         positions = []
 
@@
-        for p_name, pattern, replacement in patterns:
-            matches = list(re.finditer(pattern, masked))
-            if matches:
-                counts[p_name] = len(matches)
-                if record_positions:
-                    for match in matches:
-                        positions.append(MaskedPosition(
-                            start=match.start(),
-                            end=match.end(),
-                            mask_type=p_name,
-                            original_length=len(match.group())
-                        ))
-                masked = re.sub(pattern, replacement, masked)
+        for p_name, pattern, replacement in patterns:
+            matches = list(re.finditer(pattern, masked))
+            if matches:
+                counts[p_name] = len(matches)
+                if record_positions:
+                    for match in matches:
+                        positions.append(MaskedPosition(
+                            start=match.start(),
+                            end=match.end(),
+                            mask_type=p_name,
+                            original_length=len(match.group())
+                        ))
+                masked = re.sub(pattern, replacement, masked)
```

同様に他のメソッドも変更：
- `unmask_data`
- `save_api_key` / `load_api_key` 
- `encrypt_data` / `decrypt_data`
- `_get_encryption_key` と `_get_or_create_fernet` は削除またはラップ
- `secure_delete` は変更不要（ファイルシステム依存だが、これは別の問題）

### ステップ 2: ファサードパターンによる後方互換性ラッピング
- ファイル: `src/security_manager.py` を編集
- アプローチ: 既存のメソッドシグネチャは変更せず、内部で新しいロジックを呼び出す
- より安全な方法: クラスメソッドではなくインスタンスメソッドにリファクタリングするが、後方互換性のためクラスメソッドは残す

実際の実装案：
```python
@classmethod
def mask_sensitive_data(cls, text: str, record_positions: bool = False, config=None) -> Tuple[str, Dict[str, Any]]:
    # 設定が提供されていればそれを使い、なければレガシーモード
    if config is not None:
        # 新しいロジック
        provider = config.pattern_provider
        patterns = provider.load_patterns()
        # ... 新しいロジックで処理
    else:
        # 既存のレガシーロジック（変更なし）
        return cls._mask_sensitive_data_legacy(text, record_positions)

@classmethod  
def _mask_sensitive_data_legacy(cls, text: str, record_positions: bool = False) -> Tuple[str, Dict[str, Any]]:
    """元の実装をプライベートメソッドに移動"""
    # 元のコードをここに移動
```

ただし、ユーザーからの要求「低性能LLMでも実装可能」を考えると、ステップをもっと細かくする。

### ステップ 2-1: mask_sensitive_data の段階的変更
- まずは設定が提供された時だけ新しいロジックを走らせるテストコードを追加
- 既存動作は一切変更しない

```python
# src/security_manager.py の mask_sensitive_data メソッドの冒頭に追加
def mask_sensitive_data(cls, text: str, record_positions: bool = False, config=None) -> Tuple[str, Dict[str, Any]]:
    # NEW: Config-driven path (backward compatible)
    if config is not None:
        # Use injected config
        patterns = config.pattern_provider.load_patterns()
        masked = text
        counts = {}
        positions = []

        for p_name, pattern, replacement in patterns:
            matches = list(re.finditer(pattern, masked))
            if matches:
                counts[p_name] = len(matches)
                if record_positions:
                    for match in matches:
                        positions.append(MaskedPosition(
                            start=match.start(),
                            end=match.end(),
                            mask_type=p_name,
                            original_length=len(match.group())
                        ))
                masked = re.sub(pattern, replacement, masked)

        result = {"counts": counts}
        if record_positions:
            result["positions"] = positions

        if counts:
            logger.info(f"SecurityManager: Masked sensitive data via config: {counts}")

        return masked, result
    
    # EXISTING: Legacy behavior (unchanged)
    # ... 元のコードをここにコピー
```

### ステップ 3: 既存テストの更新と新しいテストの追加
- ファイル: `tests/test_security_manager.py` を編集
- 既存テストは後方互換性のため変更しない
- 新しいテストファイルを作成して、設定駆動モードをテスト

```python
# tests/test_security_manager_config.py
"""Tests for SecurityManager with SecurityConfig dependency injection"""

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
```

### ステップ 4: Workers環境向け統合テストの準備
- ファイル: `tests/test_security_workers.py` を新規作成
- モックを使ってWorkers環境をシミュレート

```python
"""Tests for Cloudflare Workers compatibility"""
import os
from unittest.mock import MagicMock, patch

def test_kv_pattern_provider_mock():
    """KVPatternProviderをモックでテスト"""
    from src.security.strategies_workers import KVPatternProvider
    
    # KVのモックを作成
    mock_kv = MagicMock()
    mock_kv.get.return_value = '{"patterns": [{"name": "TEST", "regex": "foo", "mask": "[FOO]", "enabled": true}]}'
    
    # KVPatternProviderにモックを注入する方法を模索
    # 実際の実装では、コンストラクタでKVバインディングを受け取るか、
    # setterで注入できるようにする必要がある
    
    # 暫定的なアプローチ: 環境変数やグローバルをモックする
    with patch.dict(os.environ, {"PII_PATTERNS_BINDING": "mock"}):
        with patch('src.security.strategies_workers.__import__') as mock_import:
            mock_workers = MagicMock()
            mock_workers.WorkersEnv.__getitem__.return_value = mock_kv
            mock_import.return_value = mock_workers
            
            provider = KVPatternProvider("PII_PATTERNS")
            patterns = provider.load_patterns()
            
            assert len(patterns) == 1
            assert patterns[0] == ("TEST", "foo", "[FOO]")
```

### ステップ 5: ドキュメントと使用例の追加
- ファイル: `README.md` または `docs/` に使用方法を追加
- 例:
```markdown
## Dependency Injection for Security Backends

Starting from v2.0, the SecurityManager supports dependency injection for backend strategies.

### Basic Usage
```python
from src.security.config import SecurityConfig
from src.security.strategies import HardcodedPatternProvider, EnvVarKeyStore, NoOpEncryption
from src.security_manager import SecurityManager

# Create custom configuration
config = SecurityConfig(
    pattern_provider=HardcodedPatternProvider(),
    key_store=EnvVarKeyStore(),
    encryption_provider=NoOpEncryption()
)

# Use with SecurityManager
masked, info = SecurityManager.mask_sensitive_data(
    "Contact: test@example.com",
    config=config
)
```

### Cloudflare Workers Usage
```python
from src.security.config import SecurityConfig
from src.security_manager import SecurityManager

# Workers environment configuration
config = SecurityConfig.from_workers_env()

# Use as usual
masked, info = SecurityManager.mask_sensitive_data(
    "Contact: test@example.com", 
    config=config
)
```
```

### ステップ 6: 最終検証と後方互換性確認
- 全ての既存テストがパスすることを確認
- 新しい機能のテストがパスすることを確認
- 設定を渡さない場合の動作が既存通りであることを確認

### フェーズ完了条件
- `src/security_manager.py` が設定注入をサポートしつつ、既存のパブリックAPIを変更していない
- `tests/test_security_manager.py` のすべての既存テストがパスする
- 新しい設定駆動モードをテストするテストファイルが存在し、パスする
- Cloudflare Workers向けの戦略が実装され、`from_workers_env` ファクトリが利用可能
- READMEまたはドキュメントに使用方法が説明されている

---
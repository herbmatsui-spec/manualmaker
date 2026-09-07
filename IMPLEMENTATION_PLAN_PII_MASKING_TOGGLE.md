# PIIマスキング オンオフ機能 実装計画書

## 目的
`SecurityManager.mask_sensitive_data()` をPDF処理パイプラインに統合し、`.env` または設定で一括オンオフ可能にする。デフォルトはオフ（後方互換性維持）。

---

## 変更対象ファイル一覧

| ファイル | 変更内容 | 優先度 |
|----------|---------|--------|
| `manual_processor/config/config.py` | 設定項目追加 | High |
| `manual_processor/src/processor/processor.py` | 条件付きマスキング呼び出し | High |
| `manual_processor/src/web/app.py` | セキュリティステータス設定参照化 | Medium |
| `manual_processor/tests/test_security.py` | テスト追加（あれば） | High |

---

## Step 1: 設定項目追加 (`config/config.py`)

### 1.1 フィールド追加
`AppConfig` クラスに以下を追加：

```python
pii_masking_enabled: bool = False  # OCR後テキストのPII自動マスキング有効/無効
```

### 1.2 環境変数読み込み
`from_env()` メソッドで以下を追加：

```python
pii_masking_enabled = os.getenv("PII_MASKING_ENABLED", "False").lower() in ("true", "1", "yes")
```

### 1.3 コンストラクタ引数追加
`cls(...)` 呼び出しに `pii_masking_enabled=pii_masking_enabled` を追加。

---

## Step 2: 処理パイプラインへの統合 (`processor.py`)

### 2.1 インポート追加
`from src.security_manager import SecurityManager` を追加。

### 2.2 マスキング適用ロジック追加
`_run_summarization()` 内、要約実行直前に以下を追加：

```python
if self.config.pii_masking_enabled:
    extracted_text, mask_info = SecurityManager.mask_sensitive_data(extracted_text, record_positions=True)
    if mask_info.get("counts"):
        logger.info(f"PII masking applied: {mask_info['counts']}")
```

### 2.3 オフ時の動作
`pii_masking_enabled = False` の場合は何もせず元のテキストを要約処理に渡す。

---

## Step 3: Web UI ステータスエンドポイント修正 (`app.py`)

### 3.1 変更内容
`/api/security/status` エンドポイント内のハードコード `"pii_masking_enabled": True` を以下に変更：

```python
"pii_masking_enabled": config.pii_masking_enabled,
```

### 3.2 配置
`from config.config import Config` または `get_instance()` で取得した `config` を参照。

---

## Step 4: テスト追加

### 4.1 新規テストケース (`test_security.py` または `test_advanced_features.py`)

```python
def test_masking_disabled_returns_original_text():
    """pii_masking_enabled=False の動作確認"""
    # processor の動作として確認
    pass

def test_config_default_masking_disabled():
    """デフォルトがFalseであること"""
    from config.config import AppConfig
    assert AppConfig.from_env().pii_masking_enabled is False
```

### 4.2 既存テスト確認
`pytest tests/ -v` で回帰テストを実行。

---

## 設定変更による動作一覧

| 環境変数 | 設定値 | 動作 |
|---------|--------|------|
| `PII_MASKING_ENABLED` | `True` / `1` / `yes` | マスキング有効 |
| `PII_MASKING_ENABLED` | `False` / `0` / `no` | マスキング無効（デフォルト） |
| 未設定 | - | マスキング無効 |

---

## 後方互換性
- デフォルト `False` のため、既存動作に影響なし。
- `/api/security/mask` エンドポイントは独立しており、手動マスキングとして利用可能。

---

## 実装後の検証項目
- [ ] `pytest tests/ -v` 全99件+ 新規テスト 成功
- [ ] `.env` で `PII_MASKING_ENABLED=True` 設定時、処理結果のテキストがマスクされる
- [ ] `.env` で未設定時、処理結果のテキストがそのまま
- [ ] `/api/security/status` が設定値を正しく返す

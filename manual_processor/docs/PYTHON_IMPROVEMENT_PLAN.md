# Python版完成度向上 実装計画書 (改善案1〜3)

## 概要

| 改善案 | ステップ範囲 | 推定工数 |
|--------|------------|----------|
| 改善案1: セキュリティ強化 | ステップ 1-12 | 5-6日 |
| 改善案2: 設定システム刷新 | ステップ 13-24 | 4-5日 |
| 改善案3: テスト・CI/CD強化 | ステップ 25-36 | 5-6日 |
| **合計** | **36ステップ** | **約15-17日** |

## 設計原則

- 各ステップは **1コミット = 1ステップ** 単位で実装
- 各ステップの最後に **検証コマンド** を明示
- 依存ステップを完了せずに次のステップに進まない
- 既存テストを破壊しない
- 低性能LLMでも実装可能な粒度（1ステップ=数十行以下）

---

# 改善案1: セキュリティ強化 (ステップ 1-12)

## ステップ 1: セキュリティ要件の明文化

**目的**: セキュリティポリシーをコード化する

**実装内容**:
1. 新規ファイル `SECURITY.md` をプロジェクトルートに作成
2. 以下の章を含める:
   - サポート対象PIIパターン一覧
   - APIキー管理方針
   - 監査ログ保持期間
   - 入力検証ルール

**ファイル**: `/workspaces/manualmaker/SECURITY.md`

**検証**:
```bash
ls SECURITY.md
```

---

## ステップ 2: 入力バリデーションユーティリティ作成

**目的**: 共通入力検証関数を実装

**実装内容**:
1. 新規ファイル `src/utils/validators.py` を作成
2. 以下の関数を実装:
   - `validate_file_size(size_mb: float, max_mb: float) -> bool`
   - `validate_pdf_content(data: bytes) -> bool` (マジックバイト `%PDF` 確認)
   - `validate_uuid(s: str) -> bool`
   - `validate_language_code(lang: str) -> bool` (5言語のみ許可)

**ファイル**: `/workspaces/manualmaker/manual_processor/src/utils/validators.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
python -c "from src.utils.validators import validate_pdf_content; print(validate_pdf_content(b'%PDF-1.4'))"
```

---

## ステップ 3: APIキー暗号化ストレージの実装

**目的**: 平文APIキーを `keyring` 経由で安全保存

**実装内容**:
1. 新規ファイル `src/security/keyring_store.py` を作成
2. 以下の関数を実装:
   - `get_api_key(service: str, username: str) -> Optional[str]`
   - `set_api_key(service: str, username: str, value: str) -> None`
   - `delete_api_key(service: str, username: str) -> None`
3. `keyring` が利用不可なら環境変数にフォールバック
4. ログには値を出力しない (キーマスキング)

**ファイル**: `/workspaces/manualmaker/manual_processor/src/security/keyring_store.py`

**検証**:
```bash
python -c "from src.security.keyring_store import get_api_key, set_api_key; set_api_key('test', 'user', 'value'); print(get_api_key('test', 'user'))"
```

---

## ステップ 4: PIIパターン定義の外部化

**目的**: ハードコードされた正規表現を設定可能に

**実装内容**:
1. 新規ファイル `config/pii_patterns.yaml` を作成
2. 以下の構造で記述:
```yaml
patterns:
  - name: EMAIL
    regex: '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    mask: "[REDACTED_EMAIL]"
  - name: PHONE_JP
    regex: '0\d{1,4}-\d{1,4}-\d{4}'
    mask: "[REDACTED_PHONE]"
  # ... 他のパターン
```
3. `src/security_manager.py` を更新して YAML から読み込む

**ファイル**:
- `/workspaces/manualmaker/manual_processor/config/pii_patterns.yaml`
- `/workspaces/manualmaker/manual_processor/src/security_manager.py` (更新)

**検証**:
```bash
python -c "from src.security_manager import SecurityManager; sm = SecurityManager(); print(sm.mask_text('Contact: test@example.com'))"
```

---

## ステップ 5: 構造化監査ログの実装

**目的**: JSON形式の監査ログ出力を追加

**実装内容**:
1. 新規ファイル `src/security/audit_logger.py` を作成
2. 以下の構造で JSON ログ出力:
```json
{"timestamp": "2026-09-07T12:00:00Z", "event": "pii_mask", "user": "system", "details": {"pattern": "EMAIL", "count": 3}}
```
3. 出力先: `logs/audit.log` (デフォルト) + stdout
4. 既存 `AuditLogger` クラスを新実装でラップ

**ファイル**:
- `/workspaces/manualmaker/manual_processor/src/security/audit_logger.py`

**検証**:
```bash
python -c "from src.security.audit_logger import AuditLogger; al = AuditLogger(); al.log('test', {'key': 'value'})"
cat logs/audit.log
```

---

## ステップ 6: CORS設定の厳格化

**目的**: ワイルドカード CORS を許可リストに変更

**実装内容**:
1. `src/web/app.py` を更新
2. `config.web_cors_origins` が環境変数 `WEB_CORS_ORIGINS` から読み込むよう変更
3. デフォルトを `["http://localhost:3000", "http://localhost:8000"]` に
4. 本番環境では `WEB_CORS_ORIGINS` を明示的に設定

**ファイル**: `/workspaces/manualmaker/manual_processor/src/web/app.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
python -c "from src.web.app import app; print([str(r) for r in app.routes if 'cors' in str(r).lower()])"
```

---

## ステップ 7: ファイルアップロード検証の追加

**目的**: アップロード時のMIMEタイプ・マジックバイト検証

**実装内容**:
1. `src/web/app.py` の upload エンドポイントを更新
2. 検証内容:
   - Content-Type が `application/pdf`
   - マジックバイト `%PDF-` で開始
   - サイズ制限
3. 失敗時は 400 エラーを返す

**ファイル**: `/workspaces/manualmaker/manual_processor/src/web/app.py`

**検証**:
```bash
python -c "from src.web.app import app; print('OK')"
pytest tests/test_web_api.py::test_upload_validation -v
```

---

## ステップ 8: レート制限ミドルウェアの実装

**目的**: API エンドポイントへの過剰リクエストを防止

**実装内容**:
1. 新規ファイル `src/web/middleware/rate_limit.py` を作成
2. シンプルな sliding window レート制限:
   - デフォルト: 60リクエスト/分/IP
3. FastAPI middleware として登録
4. 設定は環境変数から読み込み

**ファイル**:
- `/workspaces/manualmaker/manual_processor/src/web/middleware/__init__.py`
- `/workspaces/manualmaker/manual_processor/src/web/middleware/rate_limit.py`
- `/workspaces/manualmaker/manual_processor/src/web/app.py` (更新)

**検証**:
```bash
python -c "from src.web.app import app; print(len(app.user_middleware))"
```

---

## ステップ 9: セキュリティヘッダーの追加

**目的**: 基本的なセキュリティヘッダーをレスポンスに付与

**実装内容**:
1. 新規ファイル `src/web/middleware/security_headers.py` を作成
2. 以下のヘッダーを追加:
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Strict-Transport-Security: max-age=31536000`
   - `Content-Security-Policy: default-src 'self'`
3. FastAPI middleware として登録

**ファイル**:
- `/workspaces/manualmaker/manual_processor/src/web/middleware/security_headers.py`

**検証**:
```bash
python -c "from src.web.app import app; print('security headers loaded')"
```

---

## ステップ 10: センシティブログの自動マスキング

**目的**: ログに API キーや PII が含まれないことを保証

**実装内容**:
1. 新規ファイル `src/utils/log_filter.py` を作成
2. `logging.Filter` サブクラスを実装
3. 以下のパターンを自動マスク:
   - `api_key=...` 形式
   - メールアドレス
   - Bearer トークン
4. 既存ロガーに適用

**ファイル**:
- `/workspaces/manualmaker/manual_processor/src/utils/log_filter.py`
- `/workspaces/manualmaker/manual_processor/src/logger.py` (更新)

**検証**:
```bash
python -c "
import logging
from src.utils.log_filter import SensitiveDataFilter
logger = logging.getLogger('test')
logger.addFilter(SensitiveDataFilter())
logger.info('api_key=secret123')
" 2>&1 | grep -v "secret123"
```

---

## ステップ 11: セキュリティテストの追加

**目的**: セキュリティ機能の自動テスト

**実装内容**:
1. 新規ファイル `tests/test_security.py` を作成
2. 以下のテストケースを実装:
   - PII マスキング (各パターン)
   - API キーマスキング
   - 入力バリデーション
   - レート制限

**ファイル**: `/workspaces/manualmaker/manual_processor/tests/test_security.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/test_security.py -v
```

---

## ステップ 12: セキュリティ改善ドキュメント作成

**目的**: 改善内容と運用ガイドを明文化

**実装内容**:
1. `SECURITY.md` を完成させる
2. 以下の章を含める:
   - 変更履歴
   - 設定方法 (環境変数一覧)
   - インシデント対応手順
   - ベストプラクティス

**ファイル**: `/workspaces/manualmaker/SECURITY.md`

**検証**:
```bash
ls -la SECURITY.md && wc -l SECURITY.md
```

---

# 改善案2: 設定システム刷新 (ステップ 13-24)

## ステップ 13: 設定ファイル形式の設計

**目的**: YAML 設定ファイル仕様を決定

**実装内容**:
1. 新規ファイル `config/config.example.yaml` を作成
2. 以下の構造でサンプルを記述:
```yaml
app:
  name: manual-processor
  version: 2.1.0
  debug: false

paths:
  output_directory: ./output
  upload_directory: ./uploads
  log_directory: ./logs

ocr:
  provider: google_vision
  batch_size: 4
  max_retries: 3

gemini:
  model: gemini-1.5-flash
  temperature: 0.3
  max_output_tokens: 2048

web:
  host: 0.0.0.0
  port: 8000
  cors_origins:
    - http://localhost:3000

security:
  pii_masking:
    enabled: true
  audit:
    enabled: true
    retention_days: 90
```

**ファイル**: `/workspaces/manualmaker/manual_processor/config/config.example.yaml`

**検証**:
```bash
python -c "import yaml; print(yaml.safe_load(open('config/config.example.yaml')))"
```

---

## ステップ 14: Pydantic Settings 依存関係追加

**目的**: 型安全な設定管理ライブラリ導入

**実装内容**:
1. `pyproject.toml` の `dependencies` に追加:
   - `pydantic>=2.5.0`
   - `pydantic-settings>=2.1.0`
   - `pyyaml>=6.0.1`
2. `pip install` でインストール

**ファイル**: `/workspaces/manualmaker/manual_processor/pyproject.toml`

**検証**:
```bash
pip install pydantic pydantic-settings pyyaml
python -c "from pydantic_settings import BaseSettings; print('OK')"
```

---

## ステップ 15: 設定スキーマの Pydantic モデル定義

**目的**: 設定の型スキーマを定義

**実装内容**:
1. 新規ファイル `config/settings.py` を作成
2. 以下のモデルを定義:
   - `AppSettings` (app, paths)
   - `OCRSettings`
   - `GeminiSettings`
   - `WebSettings`
   - `SecuritySettings`
   - `Settings` (ルートモデル)
3. バリデーションルール:
   - ポート番号: 1-65535
   - temperature: 0.0-1.0
   - batch_size: 1-32

**ファイル**: `/workspaces/manualmaker/manual_processor/config/settings.py`

**検証**:
```bash
python -c "from config.settings import Settings; s = Settings(); print(s.app.name)"
```

---

## ステップ 16: 設定ローダーの実装

**目的**: YAML と環境変数を統合するローダー

**実装内容**:
1. 新規ファイル `config/loader.py` を作成
2. 以下の関数を実装:
   - `load_config_file(path: Path) -> dict`
   - `merge_env(config: dict) -> dict`
   - `load_settings(path: Optional[Path] = None) -> Settings`
3. 優先順位: デフォルト < YAML < 環境変数

**ファイル**: `/workspaces/manualmaker/manual_processor/config/loader.py`

**検証**:
```bash
python -c "from config.loader import load_settings; s = load_settings(); print(s)"
```

---

## ステップ 17: 既存 Config クラスのラッパー作成

**目的**: 後方互換性を維持しつつ新設定へ移行

**実装内容**:
1. `config/config.py` を更新
2. 内部で新 `Settings` を使用
3. 既存 API (`Config.get_instance()`, 属性アクセス) を維持

**ファイル**: `/workspaces/manualmaker/manual_processor/config/config.py`

**検証**:
```bash
python -c "from config.config import Config; c = Config.get_instance(); print(c.gemini_model_name)"
```

---

## ステップ 18: 環境変数の優先順位実装

**目的**: 環境変数が設定ファイルより優先される仕組み

**実装内容**:
1. `config/loader.py` を更新
2. Pydantic の `env_prefix` 機能を使用
3. 例: `GEMINI_API_KEY` 環境変数が `gemini.api_key` を上書き

**ファイル**: `/workspaces/manualmaker/manual_processor/config/loader.py`

**検証**:
```bash
GEMINI_MODEL=test-model python -c "from config.loader import load_settings; print(load_settings().gemini.model)"
```

---

## ステップ 19: 設定検証コマンドの実装

**目的**: CLI から設定の妥当性を検証

**実装内容**:
1. 新規ファイル `config/validate.py` を作成
2. 機能:
   - YAML ファイル読み込み
   - 全セクションの検証
   - エラー箇所を明示
   - 終了コード: 0=OK, 1=エラー

**ファイル**: `/workspaces/manualmaker/manual_processor/config/validate.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
python -m config.validate config/config.example.yaml
echo $?  # 0 なら成功
```

---

## ステップ 20: 設定のマイグレーションガイド作成

**目的**: 既存ユーザーへの移行手順を文書化

**実装内容**:
1. 新規ファイル `docs/CONFIG_MIGRATION.md` を作成
2. 内容:
   - 旧設定 → 新設定マッピング表
   - マイグレーション手順
   - ロールバック方法
3. README からリンク

**ファイル**: `/workspaces/manualmaker/manual_processor/docs/CONFIG_MIGRATION.md`

**検証**:
```bash
ls docs/CONFIG_MIGRATION.md
```

---

## ステップ 21: 設定パスの動的解決

**目的**: 設定ファイルパスを柔軟に指定可能に

**実装内容**:
1. `config/loader.py` を更新
2. 検索順序:
   1. 環境変数 `MANUAL_PROCESSOR_CONFIG`
   2. `./config.yaml`
   3. `~/.config/manual-processor/config.yaml`
   4. ビルトイン defaults
3. 見つからない場合はデフォルト値で起動

**ファイル**: `/workspaces/manualmaker/manual_processor/config/loader.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
python -c "from config.loader import load_settings; print(load_settings().app.name)"
```

---

## ステップ 22: 設定変更の動的反映

**目的**: ファイル監視による設定ホットリロード

**実装内容**:
1. 新規ファイル `config/watcher.py` を作成
2. `watchdog` ライブラリ使用
3. 設定ファイル変更を検出したら再ロード
4. テスト: 一時ファイル監視で動作確認

**ファイル**:
- `/workspaces/manualmaker/manual_processor/config/watcher.py`

**検証**:
```bash
python -c "from config.watcher import ConfigWatcher; print('OK')"
```

---

## ステップ 23: 既存コードベースの新設定への移行

**目的**: 内部の Config 利用箇所を新システムに統一

**実装内容**:
1. `src/` 配下を grep し `Config.get_instance()` を探す
2. 段階的に `load_settings()` に置換
3. 以下のファイルを対象:
   - `src/web/app.py`
   - `src/orchestrator.py`
   - `src/processor.py`
   - `src/security_manager.py`
4. 各置換後にテスト実行

**ファイル**: 既存ファイル群

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
grep -rn "from config.config" src/ | wc -l
pytest tests/ -v
```

---

## ステップ 24: 設定テストの追加

**目的**: 設定システム全体のテスト

**実装内容**:
1. 新規ファイル `tests/test_config.py` を作成
2. テストケース:
   - YAML 読み込み
   - 環境変数オーバーライド
   - バリデーションエラー
   - デフォルト値
   - マージロジック

**ファイル**: `/workspaces/manualmaker/manual_processor/tests/test_config.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/test_config.py -v --tb=short
```

---

# 改善案3: テスト・CI/CD強化 (ステップ 25-36)

## ステップ 25: テストカバレッジ測定の追加

**目的**: 現在のカバレッジを測定

**実装内容**:
1. `pyproject.toml` の dev 依存関係に追加:
   - `pytest-cov>=5.0.0`
   - `coverage>=7.0.0`
2. レポート生成コマンド確認:
   ```bash
   pytest --cov=src --cov=config --cov-report=html
   ```

**ファイル**: `/workspaces/manualmaker/manual_processor/pyproject.toml`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest --cov=src --cov-report=term --cov-report=html
ls htmlcov/index.html
```

---

## ステップ 26: 統合テストフィクスチャの準備

**目的**: 統合テスト用の共通フィクスチャ

**実装内容**:
1. 新規ファイル `tests/fixtures/__init__.py` 作成
2. 新規ファイル `tests/fixtures/sample_pdfs.py` 作成
3. テスト用PDF生成関数:
   - `create_sample_pdf(num_pages: int) -> bytes`
   - `create_handwritten_sample_pdf() -> bytes`
4. 1ページだけの小さなPDFを生成

**ファイル**: `/workspaces/manualmaker/manual_processor/tests/fixtures/sample_pdfs.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
python -c "from tests.fixtures.sample_pdfs import create_sample_pdf; data = create_sample_pdf(1); print(len(data))"
```

---

## ステップ 27: API 統合テストの追加

**目的**: FastAPI エンドポイントの統合テスト

**実装内容**:
1. 新規ファイル `tests/integration/test_api.py` 作成
2. テストケース:
   - `test_health_endpoint`
   - `test_config_endpoint`
   - `test_upload_valid_pdf`
   - `test_upload_invalid_file`
   - `test_upload_too_large`
3. `TestClient` を使用

**ファイル**: `/workspaces/manualmaker/manual_processor/tests/integration/test_api.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/integration/test_api.py -v
```

---

## ステップ 28: E2E テストの実装

**目的**: ファイルアップロードから結果取得までの動線

**実装内容**:
1. 新規ファイル `tests/e2e/test_full_pipeline.py` 作成
2. テストシナリオ:
   1. サンプル PDF をアップロード
   2. 処理開始
   3. 進捗をポーリング
   4. 結果取得
   5. 出力ファイルダウンロード
3. Gemini API はモック化

**ファイル**: `/workspaces/manualmaker/manual_processor/tests/e2e/test_full_pipeline.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/e2e/test_full_pipeline.py -v
```

---

## ステップ 29: パフォーマンステストの追加

**目的**: 性能ベンチマーク測定

**実装内容**:
1. `pyproject.toml` の dev 依存に追加:
   - `pytest-benchmark>=4.0.0`
2. 新規ファイル `tests/performance/test_benchmarks.py` 作成
3. ベンチマーク対象:
   - PDF レンダリング
   - テキスト処理
   - PII マスキング
   - 設定読み込み

**ファイル**:
- `/workspaces/manualmaker/manual_processor/pyproject.toml`
- `/workspaces/manualmaker/manual_processor/tests/performance/test_benchmarks.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/performance/test_benchmarks.py --benchmark-only
```

---

## ステップ 30: セキュリティスキャンツール導入

**目的**: bandit による自動セキュリティ検査

**実装内容**:
1. `pyproject.toml` の dev 依存に追加:
   - `bandit>=1.7.0`
   - `pip-audit>=2.6.0`
2. 設定ファイル `pyproject.toml` に追加:
```toml
[tool.bandit]
exclude_dirs = ["tests", "build"]
```
3. 手動実行確認:
   ```bash
   bandit -r src/
   ```

**ファイル**: `/workspaces/manualmaker/manual_processor/pyproject.toml`

**検証**:
```bash
pip install bandit pip-audit
bandit -r src/ --skip B101
```

---

## ステップ 31: GitHub Actions ワークフロー更新

**目的**: CI ワークフローの改善

**実装内容**:
1. 既存 `.github/workflows/test.yml` を更新
2. ジョブ追加:
   - `lint`: flake8
   - `security`: bandit, pip-audit
   - `test`: pytest with coverage
   - `benchmark`: パフォーマンステスト
3. Python 3.8, 3.9, 3.10, 3.11, 3.12 でマトリクステスト

**ファイル**: `/workspaces/manualmaker/.github/workflows/test.yml`

**検証**:
```bash
cat .github/workflows/test.yml | head -30
```

---

## ステップ 32: カバレッジバッジの追加

**目的**: README にカバレッジバッジを表示

**実装内容**:
1. `README.md` の冒頭に以下を追加:
```markdown
[![Coverage](https://codecov.io/gh/USER/REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/USER/REPO)
```
2. codecov.io 連携設定 (任意)
3. 代替案: GitHub Actions でカバレッジレポート生成

**ファイル**: `/workspaces/manualmaker/manual_processor/README.md`

**検証**:
```bash
grep -i coverage README.md
```

---

## ステップ 33: テスト用 Makefile 作成

**目的**: テスト実行の簡易化

**実装内容**:
1. 新規ファイル `Makefile` を作成
2. ターゲット:
   - `make test` - 全テスト実行
   - `make test-unit` - ユニットテストのみ
   - `make test-integration` - 統合テスト
   - `make coverage` - カバレッジレポート
   - `make lint` - リント
   - `make security` - セキュリティスキャン
   - `make benchmark` - ベンチマーク
   - `make clean` - 成果物削除

**ファイル**: `/workspaces/manualmaker/manual_processor/Makefile`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
make help
```

---

## ステップ 34: テストヘルパー関数の追加

**目的**: テストの boilerplate 削減

**実装内容**:
1. 新規ファイル `tests/utils/helpers.py` 作成
2. ヘルパー:
   - `create_temp_dir() -> Path`
   - `cleanup_temp_dir(path: Path)`
   - `assert_valid_pdf(data: bytes)`
   - `mock_gemini_response(text: str)`
   - `mock_vision_response(text: str)`
3. 既存テストをリファクタリングして活用

**ファイル**: `/workspaces/manualmaker/manual_processor/tests/utils/helpers.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
python -c "from tests.utils.helpers import create_temp_dir; print(create_temp_dir())"
```

---

## ステップ 35: カバレッジレポート解析スクリプト

**目的**: カバレッジ低下の検出

**実装内容**:
1. 新規ファイル `scripts/check_coverage.py` 作成
2. 機能:
   - coverage.json を読み込み
   - 各モジュールのカバレッジを集計
   - 80% 未満のモジュールをリストアップ
   - 終了コード 0 (OK) / 1 (NG)
3. CI で実行される前提

**ファイル**: `/workspaces/manualmaker/manual_processor/scripts/check_coverage.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
python scripts/check_coverage.py
echo $?
```

---

## ステップ 36: 統合ドキュメント作成

**目的**: 全改善内容をまとめたサマリ

**実装内容**:
1. `docs/IMPROVEMENTS.md` を作成
2. 内容:
   - 改善案1〜3 のサマリ
   - 36ステップの完了状況
   - 残課題
   - 今後のロードマップ
3. README からリンク

**ファイル**: `/workspaces/manualmaker/manual_processor/docs/IMPROVEMENTS.md`

**検証**:
```bash
ls docs/IMPROVEMENTS.md && wc -l docs/IMPROVEMENTS.md
```

---

# 全体スケジュール

| Week | ステップ | 内容 |
|------|----------|------|
| Week 1 | 1-6 | セキュリティ強化 (前半) |
| Week 2 | 7-12 | セキュリティ強化 (後半) |
| Week 2-3 | 13-18 | 設定システム刷新 (前半) |
| Week 3-4 | 19-24 | 設定システム刷新 (後半) |
| Week 4-5 | 25-30 | テスト強化 |
| Week 5-6 | 31-36 | CI/CD 統合 |

---

# 検証チェックリスト

各ステップ完了時に以下を確認:

- [ ] コードが構文エラーなしで実行できる
- [ ] 新規ファイルが指定パスに存在する
- [ ] 既存テストが破壊されない
- [ ] 検証コマンドが期待通りの出力を返す
- [ ] 1コミットに収まる変更量である
- [ ] 低性能LLMでも実装可能な粒度である (50行以下)

---

# トラブルシューティング

## 問題: 既存テストが失敗する

**対処**:
1. 影響範囲を `git diff` で確認
2. 該当テストを修正
3. 必要に応じて新規テスト追加

## 問題: 依存関係インストールエラー

**対処**:
1. Python バージョン確認: `python --version`
2. 仮想環境使用: `python -m venv venv`
3. 個別インストール: `pip install <package>`

## 問題: カバレッジが目標未達

**対処**:
1. `htmlcov/index.html` で未カバー箇所確認
2. 該当モジュールにテスト追加
3. テストヘルパー活用

---

# 参考リンク

- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Bandit: https://bandit.readthedocs.io/
- pytest-benchmark: https://pytest-benchmark.readthedocs.io/
- GitHub Actions: https://docs.github.com/en/actions

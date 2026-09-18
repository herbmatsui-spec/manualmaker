# Phase 2: 本番強化 - 実装計画書

## 概要
Phase 1で構築した基盤の上で、本番運用に耐えうる非同期処理、構造化ログ、監査ログ、外部APIタイムアウト、依存関係固定を実装する。

**目標期間**: 2週間  
**前提**: Phase 1 (Redis移行、認証、ヘルスチェック) 完了済み

---

## Step 1: Celeryワーカー基盤の構築

### 目的
重いPDF処理をバックグラウンドで非同期実行する基盤を作る

### 作業内容
1. `requirements.txt` / `setup.py` に追加：
   - `celery>=5.3.0`
   - `flower>=2.0.0` (監視用)
2. `manual_processor/config/settings.py` に `CelerySettings` 追加：
   - `broker_url: str = "redis://localhost:6379/1"`
   - `result_backend: str = "redis://localhost:6379/2"`
   - `task_serializer: str = "json"`
   - `result_serializer: str = "json"`
   - `worker_prefetch_multiplier: int = 1`
   - `task_acks_late: bool = True`
3. `manual_processor/workers/celery_app.py` 新規作成：
   - `Celery` インスタンス作成
   - 設定読み込み
   - タスクルート設定
4. `manual_processor/workers/__init__.py` 作成

### 確認方法
- `celery -A manual_processor.workers.celery_app worker --loglevel=info` でワーカー起動
- `flower` でダッシュボードアクセス可能

---

## Step 2: PDF処理タスクの定義

### 目的
`DocumentProcessor.process_pdf` をCeleryタスクとして実行可能にする

### 作業内容
1. `manual_processor/workers/tasks/pdf_tasks.py` 新規作成
2. `process_pdf_task` タスク定義：
   ```python
   @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
   def process_pdf_task(self, file_id: str, options: dict) -> dict:
       # 既存の process_pdf ロジックをここで実行
       # 進捗更新は Redis (ProcessService) 経由で行う
   ```
3. 進捗コールバックを `ProcessService.update_process_progress` に置換
4. 例外時は `self.retry(exc=e)` でリトライ
4. 成功/失敗時に結果を `ProcessService` に保存

### 確認方法
- タスクキュー投入 → ワーカーが処理 → 進捗がRedisに記録 → 完了時に結果取得可能

---

## Step 3: APIエンドポイントの非同期化

### 目的
`/api/process/{fileId}` を即座に返し、バックグラウンドで処理する

### 作業内容
1. `manual_processor/src/web/app.py` の `process_pdf_api` を書き換え：
   - ファイル存在確認のみ実行
   - `ProcessService.save_process_state` で初期状態保存
   - `process_pdf_task.delay(file_id, options)` でタスク投入
   - 即座に `{"status": "accepted", "file_id": file_id}` 返却
2. クライアント側は `/api/process/{fileId}` でポーリングして進捗取得
3. 既存の同期処理パスは削除または非推奨化

### 確認方法
- 大きなPDFアップロード → `/api/process/{fileId}` 即座にレスポンス
- ポーリングで進捗 0→100% 確認
- 完了後 `/api/results/{fileId}` で結果取得

---

## Step 4: 構造化ログの導入

### 目的
全ログをJSON形式にし、相関IDでトレース可能にする

### 作業内容
1. `requirements.txt` / `setup.py` に `python-json-logger>=2.0.0` 追加
2. `manual_processor/src/utils/logging_config.py` 新規作成：
   - `JsonFormatter` クラス: `timestamp`, `level`, `logger`, `message`, `correlation_id`, `file_id`, `user_id` フィールド
   - `setup_logging()`: ルートロガーにハンドラ設定
   - `get_logger(name: str)`: 相関ID対応ロガー取得
3. `manual_processor/src/utils/correlation.py` 新規作成：
   - `CorrelationContext` コンテキストマネージャ
   - `get_correlation_id() -> str` (UUID生成またはヘッダーから取得)
   - `set_correlation_id(id: str)`
4. `manual_processor/src/web/app.py` にミドルウェア追加：
   - リクエストごとに `X-Correlation-ID` 生成/継承
   - レスポンスヘッダーに `X-Correlation-ID` 付与
5. 全モジュールの `logger = logging.getLogger(__name__)` を `get_logger(__name__)` に置換

### 確認方法
- リクエスト実行 → ログがJSON形式で出力
- 同一リクエストのログ全てに同じ `correlation_id` 含む
- `jq` でフィルタリング可能

---

## Step 5: 監査ログの永続化・署名・ローテーション

### 目的
改ざん検知可能で長期保存できる監査ログを実現

### 作業内容
1. `manual_processor/src/security/audit_logger.py` を全面書き換え：
   - ストレージ: Redis Stream (`audit:log`) + 定期的なファイル/DBアーカイブ
   - エントリ構造: `timestamp`, `user_id`, `action`, `resource`, `details`, `correlation_id`, `signature`
   - 署名: HMAC-SHA256 (鍵: `AUDIT_HMAC_KEY` 環境変数)
   - `log_entry()`: エントリ作成→署名→Redis Stream追加
   - `verify_logs(start: str, end: str) -> List[dict]`: 署名検証付き取得
2. ローテーション:
   - `scripts/archive_audit_logs.py` 作成
   - 日次でRedis Streamから前日分をファイル/DBにアーカイブ
   - Redisでは直近7日のみ保持
3. `manual_processor/src/security_manager.py` の `AuditLogger` を新実装に委譲

### 確認方法
- 監査ログ記録 → Redis Streamに署名付きで保存
- `verify_logs` で改ざん検知 (署名不一致)
- アーカイブスクリプト実行 → ファイル出力、Redisから削除

---

## Step 6: 外部API呼び出しにタイムアウト・リトライ設定

### 目的
Gemini、Vision API 呼び出しのハング防止

### 作業内容
1. `manual_processor/config/settings.py` に `ExternalAPISettings` 追加：
   - `gemini_timeout: int = 30`
   - `gemini_max_retries: int = 3`
   - `vision_timeout: int = 30`
   - `vision_max_retries: int = 3`
   - `connect_timeout: int = 10`
2. `manual_processor/src/gemini_processor.py` 修正：
   - `genai.Client` に `http_options=HttpOptions(timeout=...)` 渡す
   - `_generate_with_retry` の `retry` デコレータに `stop_after_attempt(config.gemini_max_retries)` 設定
3. `manual_processor/src/ocr_processor.py` 修正：
   - `vision.ImageAnnotatorClient` に `client_options=ClientOptions(api_key=..., timeout=...)` 
   - `perform_ocr_on_image` の `retry` 設定を設定値から取得
4. `httpx` または `aiohttp` 使用箇所全てにタイムアウト設定

### 確認方法
- モックで遅延応答 → 設定秒数でタイムアウト
- 一時的エラー → 設定回数リトライ後失敗

---

## Step 7: 依存関係の完全ピン止めと脆弱性スキャン

### 目的
再現可能なビルドと既知脆弱性の排除

### 作業内容
1. `requirements.txt` 全パッケージを `==` で完全ピン止め
   - `pip freeze > requirements-lock.txt` で生成
2. `setup.py` の `install_requires` も同様に固定版作成 (`setup-lock.py`)
3. `pip-audit` 実行スクリプト `scripts/scan_vulns.py` 作成：
   - `pip-audit -r requirements-lock.txt --format=json`
   - CVE検出時は CI で失敗
4. `Dependabot` または `Renovate` 設定ファイル追加 (`.github/dependabot.yml`)
5. `pyproject.toml` に `[tool.pip-audit]` 設定追加

### 確認方法
- `pip-audit` パス
- `pip install -r requirements-lock.txt` で再現可能
- Dependabot PR が自動作成される

---

## Step 8: プロメテウスメトリクスの拡充

### 目的
本番監視に必要なメトリクスを網羅

### 作業内容
1. `manual_processor/src/observability/metrics.py` 拡張：
   - HTTP: `http_requests_total`, `http_request_duration_seconds`, `http_request_size_bytes`, `http_response_size_bytes`
   - ビジネス: `pdf_upload_total`, `pdf_process_total`, `pdf_process_duration_seconds`, `pdf_process_success_total`, `pdf_process_failure_total`
   - システム: `worker_queue_size`, `worker_processing`, `redis_connected`, `active_websockets`
   - 外部API: `gemini_api_calls_total`, `gemini_api_duration_seconds`, `vision_api_calls_total`, `vision_api_duration_seconds`
2. `manual_processor/src/web/app.py` にメトリクス記録ミドルウェア追加
3. `/metrics` エンドポイントで全メトリクス公開

### 確認方法
- `curl /metrics` で全メトリクス取得
- 負荷テスト実行 → メトリクスが正しく増加
- Grafanaダッシュボードで可視化可能

---

## Step 9: グレースフルシャットダウン実装

### 目的
デプロイ・スケール時のリクエスト断絶防止

### 作業内容
1. `manual_processor/src/web/app.py` に `lifespan` ハンドラ追加：
   - 起動時: Redis接続、Celery接続、ワーカー登録
   - 終了シグナル受信: 新規リクエスト受付停止 → 処理中リクエスト完了待ち (最大30秒) → 接続クローズ
2. Celeryワーカーにもシグナルハンドラ追加：
   - 現在タスク完了まで待機 → 終了
3. Kubernetes `preStop` フック用エンドポイント `/api/health/ready` 追加

### 確認方法
- `SIGTERM` 送信 → 進行中リクエスト完了後終了
- `/api/health/ready` が `false` を返す期間中は新規トラフィック来ない

---

## Step 10: エラーハンドリングの統一・詳細化

### 目的
ユーザーには安全なメッセージ、開発者には詳細な情報を提供

### 作業内容
1. `manual_processor/src/exceptions.py` 拡張：
   - 例外階層: `AppError` → `ValidationError`, `AuthenticationError`, `AuthorizationError`, `NotFoundError`, `ExternalServiceError`, `InternalError`
   - 各例外に `user_message` (安全), `debug_info` (詳細), `error_code` 付与
2. `manual_processor/src/web/app.py` のグローバル例外ハンドラ書き換え：
   - `AppError` 派生: `user_message` と `error_code` 返却
   - それ以外: `InternalError` としてログ出力、汎用メッセージ返却
   - 本番環境ではスタックトレース非表示
3. 全 `raise HTTPException` をカスタム例外に置換

### 確認方法
- バリデーションエラー → `{"error": "入力が正しくありません", "code": "VALIDATION_ERROR"}`
- 内部エラー → `{"error": "内部エラーが発生しました", "code": "INTERNAL_ERROR"}` + ログに詳細

---

## Step 11: 統合テストスイートの追加

### 目的
Phase 1-2の機能が連携して動くことを自動検証

### 作業内容
1. `tests/integration/test_full_flow.py` 新規作成：
   - テスト用Redisコンテナ起動 (testcontainers)
   - 認証フロー: ログイン → トークン取得 → API呼び出し
   - アップロード → 処理投入 → 進捗ポーリング → 結果取得
   - WebSocket進捗通知受信
   - レート制限動作確認
   - 監査ログ記録確認
2. `tests/conftest.py` に共通フィクスチャ追加
3. `pytest.ini` に `integration` マーカー追加

### 確認方法
- `pytest tests/integration/ -v` 全パス
- CIパイプラインに統合テストステージ追加

---

## Step 12: 負荷テストスクリプトの作成

### 目的
キャパシティプランニングとボトルネック特定

### 作業内容
1. `locustfile.py` 新規作成：
   - ユーザーシナリオ: アップロード → 処理 → 結果取得 → ダウンロード
   - 同時接続数: 10, 50, 100, 200 で段階的実行
   - 目標: p99レイテンシ < 2秒、エラー率 < 1%
2. `scripts/load_test.sh` 作成：
   - Locustヘッドレスモード実行
   - 結果をHTMLレポート出力
   - しきい値超過時は非ゼロ終了
3. `benchmark/` ディレクトリにサンプルPDF配置

### 確認方法
- `locust -f locustfile.py --headless -u 100 -r 10 --run-time 5m`
- HTMLレポートでボトルネック特定

---

## 依存関係マッピング

```
Step 1 (Celery基盤)     → Step 2, 3
Step 2 (PDFタスク)       → Step 3
Step 3 (API非同期化)      → Step 11
Step 4 (構造化ログ)       → Step 5, 10, 11
Step 5 (監査ログ強化)      → Step 11
Step 6 (外部APIタイムアウト) → Step 2, 3, 11
Step 7 (依存関係固定)      → 全Step (最初にやるべき)
Step 8 (メトリクス拡充)      → Step 11, 12
Step 9 (グレースフル停止)    → Step 3
Step 10 (エラー統一)        → Step 3, 11
Step 11 (統合テスト)        → Step 1-10 全て
Step 12 (負荷テスト)        → Step 1-11 全て
```

## 推奨実施順序

| 週 | Steps | 備考 |
|----|-------|------|
| 1前半 | 7, 1, 2 | 依存固定→Celery基盤→タスク定義 |
| 1後半 | 3, 4, 6 | API非同期化→ログ→外部API保護 |
| 2前半 | 5, 8, 9 | 監査ログ→メトリクス→シャットダウン |
| 2後半 | 10, 11, 12 | エラー統一→統合テスト→負荷テスト |

---

*各Stepは1-2時間で完了する粒度。Phase 1完了を前提とする。*
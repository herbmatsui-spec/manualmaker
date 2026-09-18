# Phase 1: セキュリティと安定性 - 実装計画書

## 概要
本フェーズでは、商用リリースに必須のセキュリティ機能と本番環境での安定稼働に必要な基盤を構築する。

**目標期間**: 2週間  
**対象**: Python Web API (FastAPI)

---

## Step 1: Redis接続設定の追加

### 目的
インメモリグローバルステートをRedisに移行するための基盤を作る

### 作業内容
1. `manual_processor/config/settings.py` に `RedisSettings` クラスを追加
   - `host: str = "localhost"`
   - `port: int = 6379`
   - `db: int = 0`
   - `password: Optional[str] = None`
   - `ssl: bool = False`
2. `manual_processor/config/config.py` の `AppConfig` に `redis` プロパティを追加
3. `requirements.txt` と `setup.py` に `redis>=5.0.0` を追加
4. `.env.example` に `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_SSL` を追加

### 確認方法
- `python -c "from config.config import Config; c=Config.get_instance(); print(c.redis.host)"` で値が取れること

---

## Step 2: Redisクライアントシングルトンの作成

### 目的
アプリケーション全体で共有するRedis接続プールを提供する

### 作業内容
1. `manual_processor/src/utils/redis_client.py` を新規作成
2. `get_redis_client()` 関数を実装
   - `redis.ConnectionPool` を使用
   - 接続失敗時のリトライロジック（最大3回、指数バックオフ）
   - ヘルスチェック用 `ping()` メソッド
3. `close_redis_client()` 関数でクリーンアップ

### 確認方法
- `python -c "from src.utils.redis_client import get_redis_client; r=get_redis_client(); print(r.ping())"` で `True` が返ること

---

## Step 3: アップロードファイルメタデータのRedis移行

### 目的
`UPLOADED_FILES` グローバル辞書をRedisに置き換える

### 作業内容
1. `manual_processor/src/services/upload_service.py` を新規作成
2. 以下のメソッドを実装：
   - `save_upload_meta(file_id: str, meta: dict) -> bool`
   - `get_upload_meta(file_id: str) -> Optional[dict]`
   - `list_upload_metas() -> List[dict]`
   - `delete_upload_meta(file_id: str) -> bool`
3. キー形式: `upload:{file_id}`、TTL: 24時間
4. `manual_processor/src/web/app.py` の `UPLOADED_FILES` 参照を全て `UploadService` に置換

### 確認方法
- `/api/upload` でアップロード → `/api/uploads` で一覧取得 → 再起動後もデータが残ること

---

## Step 4: 処理結果のRedis移行

### 目的
`PROCESSING_RESULTS` グローバル辞書をRedisに置き換える

### 作業内容
1. `manual_processor/src/services/process_service.py` を新規作成
2. 以下のメソッドを実装：
   - `save_process_state(file_id: str, state: dict) -> bool`
   - `get_process_state(file_id: str) -> Optional[dict]`
   - `update_process_progress(file_id: str, progress: int, stage: str, status: str) -> bool`
3. キー形式: `process:{file_id}`、TTL: 48時間
4. `manual_processor/src/web/app.py` の `PROCESSING_RESULTS` 参照を全て `ProcessService` に置換

### 確認方法
- `/api/process/{fileId}` で処理開始 → `/api/process/{fileId}` で進捗取得 → 再起動後も状態が残ること

---

## Step 5: WebSocket接続管理のPub/Sub移行

### 目的
`ACTIVE_WEBSOCKETS` グローバル辞書をRedis Pub/Subに置き換える

### 作業内容
1. `manual_processor/src/services/websocket_service.py` を新規作成
2. 以下を実装：
   - `register_connection(file_id: str, websocket: WebSocket) -> None`
   - `unregister_connection(file_id: str) -> None`
   - `broadcast_progress(file_id: str, message: dict) -> None`
3. Redis Pub/Sub チャンネル: `ws:{file_id}`
4. `manual_processor/src/web/app.py` の `ACTIVE_WEBSOCKETS` と `websocket_progress` エンドポイントを書き換え

### 確認方法
- 複数プロセスでWebSocket接続 → 片方からブロードキャスト → 全プロセスのクライアントに届くこと

---

## Step 6: JWT認証ミドルウェアの実装

### 目的
APIエンドポイントを保護する認証機構を追加する

### 作業内容
1. `requirements.txt` / `setup.py` に `python-jose[cryptography]>=3.3.0`, `passlib[bcrypt]>=1.7.4` を追加
2. `manual_processor/config/settings.py` に `AuthSettings` 追加
   - `secret_key: str` (必須、環境変数から)
   - `algorithm: str = "HS256"`
   - `access_token_expire_minutes: int = 30`
   - `refresh_token_expire_days: int = 7`
3. `manual_processor/src/auth/jwt_handler.py` 新規作成
   - `create_access_token(data: dict) -> str`
   - `create_refresh_token(data: dict) -> str`
   - `decode_token(token: str) -> dict`
   - `verify_password(plain: str, hashed: str) -> bool`
   - `get_password_hash(password: str) -> str`
5. `manual_processor/src/auth/middleware.py` 新規作成
   - `AuthMiddleware` クラス: `Authorization: Bearer <token>` ヘッダー検証
   - 公開エンドポイント除外リスト: `/api/health`, `/api/config`, `/api/i18n/*`, `/api/security/patterns`, `/docs`, `/openapi.json`
6. `manual_processor/src/web/app.py` にミドルウェア追加

### 確認方法
- トークンなしで `/api/upload` → 401
- 有効トークンで `/api/upload` → 200
- 期限切れトークン → 401

---

## Step 7: APIキーベース認証の実装（サービス間通信用）

### 目的
JWT以外にAPIキーでの認証もサポートする

### 作業内容
1. `manual_processor/src/auth/api_key.py` 新規作成
2. `APIKeyManager` クラス実装：
   - `generate_key(prefix: str = "mk") -> Tuple[str, str]` (生キー、ハッシュ)
   - `verify_key(raw_key: str, hashed_key: str) -> bool`
   - `list_keys() -> List[dict]`
   - `revoke_key(key_id: str) -> bool`
3. キーはRedisに `apikey:{key_id}` で保存（ハッシュのみ保存）
4. `APIKeyMiddleware` で `X-API-Key` ヘッダー検証
5. JWTとAPIキーのどちらかが有効なら通す

### 確認方法
- `X-API-Key` ヘッダーでアクセス可能
- 無効キーで401
- 取り消し済みキーで401

---

## Step 8: レート制限ミドルウェアの実装

### 目的
DoS攻撃防止と公平なリソース配分

### 作業内容
1. `requirements.txt` / `setup.py` に `slowapi>=0.1.9` を追加
2. `manual_processor/src/auth/rate_limiter.py` 新規作成
3. `get_rate_limiter()` で `Limiter` インスタンス作成
   - ストレージ: Redis (`redis://...`)
   - デフォルト: `100/minute` per IP
   - 認証済みユーザー: `1000/minute` per user_id
   - アップロード: `10/minute` per user
3. `manual_processor/src/web/app.py` に `app.state.limiter = limiter` 追加
4. 主要エンドポイントに `@limiter.limit()` デコレータ付与

### 確認方法
- 短時間に大量リクエスト → 429 エラー
- レスポンスヘッダーに `X-RateLimit-Limit`, `X-RateLimit-Remaining` 含む

---

## Step 9: 入力検証・サニタイズの強化

### 目的
パストラバーサル、インジェクション攻撃を防ぐ

### 作業内容
1. `manual_processor/src/utils/validators.py` を拡張
2. 以下の関数を追加/強化：
   - `sanitize_path_component(name: str) -> str`: パスコンポーネント用サニタイズ
   - `validate_drive_folder_name(name: str) -> bool`: Google Driveフォルダ名検証
   - `validate_file_id(file_id: str) -> bool`: 既存の強化
   - `sanitize_filename_strict(filename: str) -> str`: より厳格なファイル名サニタイズ
3. `manual_processor/src/web/app.py` の全入力箇所で使用
   - `file_id` パラメータ: `validate_file_id`
   - `folder_name`: `validate_drive_folder_name`
   - アップロードファイル名: `sanitize_filename_strict`

### 確認方法
- `../../etc/passwd` 等のパストラバーサル入力 → 400エラー
- 特殊文字を含むDriveフォルダ名 → 400エラー

---

## Step 10: 暗号鍵導出の強化 (PBKDF2)

### 目的
弱い鍵導出をPBKDF2に置き換える

### 作業内容
1. `manual_processor/src/security/crypto_utils.py` 新規作成
2. 以下を実装：
   - `derive_key(password: str, salt: bytes, iterations: int = 100000) -> bytes`: PBKDF2-HMAC-SHA256
   - `generate_salt() -> bytes`: 16バイト乱数
   - `encrypt_data(data: bytes, password: str) -> Tuple[bytes, bytes]`: (salt, ciphertext)
   - `decrypt_data(salt: bytes, ciphertext: bytes, password: str) -> bytes`
3. `manual_processor/src/security_manager.py` の `_get_encryption_key`, `_get_or_create_fernet` を新実装に置換
4. 既存暗号化データの移行スクリプト `scripts/migrate_encryption.py` 作成

### 確認方法
- 暗号化→復号で元データと一致
- 異なるパスワードで復号失敗
- 移行スクリプトで既存データ復号可能

---

## Step 11: 起動時設定検証の追加

### 目的
必須設定が揃っていない状態での起動を防ぐ

### 作業内容
1. `manual_processor/config/config.py` の `validate()` メソッドを拡張
   - `SECRET_KEY` 必須チェック
   - `REDIS_HOST` 接続確認
   - `GEMINI_API_KEY` または `GOOGLE_API_KEY` 存在確認
   - `ENCRYPTION_KEY` 存在確認（暗号化有効時）
   - 出力ディレクトリ書き込み権限確認
2. `main.py` で起動時に `config.validate()` 呼び出し、エラー時は即座に終了
3. エラーメッセージに不足項目と設定方法を明記

### 確認方法
- 必須環境変数なしで起動 → 明確なエラーメッセージで終了
- 全設定正しい場合 → 正常起動

---

## Step 12: ヘルスチェックの依存関係確認追加

### 目的
`/api/health` で実際のサービス可用性を返す

### 作業内容
1. `manual_processor/src/services/health_service.py` 新規作成
2. `HealthChecker` クラス実装：
   - `check_redis() -> bool`: `ping()` 実行
   - `check_gemini_api() -> bool`: 軽量リクエストで疎通確認（タイムアウト5秒）
   - `check_google_vision() -> bool`: クライアント初期化確認
   - `check_disk_space() -> bool`: 出力ディレクトリの空き容量 > 100MB
3. `/api/health` エンドポイント書き換え
   - 全チェック実行、全成功なら `{"status": "ok", "checks": {...}}`
   - 1つでも失敗なら `{"status": "degraded", "checks": {...}}` + 503
   - 詳細: `checks.redis`, `checks.gemini`, `checks.vision`, `checks.disk`

### 確認方法
- 全サービス正常 → `{"status": "ok", ...}`
- Redis停止 → `{"status": "degraded", "checks": {"redis": false, ...}}` + 503

---

## 依存関係マッピング

```
Step 1 (Redis設定)      → Step 2, 3, 4, 5, 8
Step 2 (Redisクライアント) → Step 3, 4, 5, 8
Step 3 (アップロード移行)   → Step 4, 5
Step 4 (処理結果移行)      → Step 5
Step 5 (WebSocket移行)     → 独立
Step 6 (JWT認証)          → Step 7, 8
Step 7 (APIキー認証)       → Step 8
Step 8 (レート制限)        → Step 6, 7
Step 9 (入力検証)          → 独立
Step 10 (暗号強化)         → 独立
Step 11 (起動時検証)       → Step 1, 6, 10
Step 12 (ヘルスチェック)    → Step 1, 2
```

## 優先順位

| Priority | Steps | 理由 |
|----------|-------|------|
| 1 | 1, 2, 3, 4 | 状態管理のRedis移行が最優先（再起動耐性） |
| 2 | 5 | WebSocketもステートレス化 |
| 3 | 6, 7, 8 | 認証・認可・レート制限はセキュリティ必須 |
| 4 | 9 | 入力検証で攻撃防止 |
| 5 | 10 | 暗号化の安全性 |
| 6 | 11, 12 | 運用品質向上 |

---

*各Stepは1-2時間で完了する粒度で設計。順番に実装すれば確実に完了する。*
# API Reference

Web サーバ (FastAPI) は以下の REST エンドポイントを提供します。

## Health & Status

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/health` | ヘルスチェック |
| GET | `/api/config` | 公開可能な設定情報 |
| GET | `/metrics` | Prometheus 形式メトリクス |
| GET | `/api/observability/status` | 観測性の有効状態 |

## Processing

| Method | Path | 説明 |
|--------|------|------|
| POST | `/api/upload` | PDF アップロード |
| GET | `/api/progress/{file_id}` | 進捗取得 (SSE/WebSocket) |
| GET | `/api/download/{file_id}/{format}` | 成果物ダウンロード |
| POST | `/api/process/options` | プロンプト設定 |

## i18n

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/i18n/languages` | 利用可能言語一覧 |
| GET | `/api/i18n/translations/{lang}` | 言語別翻訳取得 |
| POST | `/api/i18n/set` | 言語設定 |
| POST | `/api/i18n/detect` | テキストの言語検出 |

## Security

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/security/status` | セキュリティ機能の状態 |
| POST | `/api/security/mask` | テキストのマスキング |
| GET | `/api/security/audit` | 監査ログ取得 |

## Google Drive

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/drive/auth` | 認証 URL 取得 |
| GET | `/api/drive/callback` | OAuth コールバック |
| POST | `/api/drive/upload/{file_id}` | アップロード |
| POST | `/api/drive/revoke` | 認証解除 |

## 主要 Python API

```python
from config.config import AppConfig
from src.observability import metrics as obs

config = AppConfig.get_instance()
with obs.job_timer("process_file"):
    result = orchestrator.process_file(pdf_path)
```
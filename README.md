# 手書きマニュアル処理システム (Manual Maker)

[![Workers Tests](https://img.shields.io/badge/workers-261%20passing-brightgreen.svg)](manual-maker-workers)
[![Python Tests](https://img.shields.io/badge/python-1332%20passing-brightgreen.svg)](manual_processor)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-blue.svg)](manual-maker-workers)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%2F%20Linux%20%2F%20macOS-lightgrey.svg)]()

スキャンされた手書きマニュアル（PDF）を読み込み、**Google Gemini API** および **Google Cloud Vision API** を活用して高精度なOCR解析・初心者向けの要約および構造化を行い、**PDF**・**Word文書**・**音声ファイル(MP3/WAV)**・**フローチャート画像(PNG)** の複数フォーマットで自動出力するシステムです。

---

## 📦 リポジトリ構成

本リポジトリには **別々に動作する 2 つのコンポーネント** が含まれます。用途もデプロイ先も異なります。

| | `manual-maker-workers/` | `manual_processor/` |
|---|---|---|
| 技術 | TypeScript (Hono + Zod OpenAPI) | Python (FastAPI) |
| 実行環境 | Cloudflare Workers | ローカル / デスクトップ |
| デプロイ | **あり**（Wrangler で Cloudflare へ） | なし（`pip install` してローカル実行） |
| 検証コマンド | `npm test` | `pytest tests/` |
| 役割 | API プロキシ、R2 / KV / DO によるアップロード・進捗管理、PII マスキング | Gemini / Vision を用いた PDF 解析とローカル出力（PDF / DOCX / 音声） |

**Cloudflare にデプロイするのは `manual-maker-workers/` だけです。**
対応する Wrangler 設定は [`manual-maker-workers/wrangler.toml`](manual-maker-workers/wrangler.toml) のみです。リポジトリルートに `wrangler.toml` は置きません（誤デプロイ防止のため）。

### Workers の主なエンドポイント

| メソッド | パス | 概要 |
|---|---|---|
| GET | `/api/health` | ヘルスチェック |
| GET | `/api/doc` | OpenAPI 仕様 |
| POST | `/api/upload` | multipart アップロード → R2（`WEB_UPLOAD_MAX_MB` を実サイズで検証） |
| POST | `/api/gemini/{model}/{method}` | Gemini プロキシ（API キーをブラウザに露出させない） |
| POST | `/api/vision/annotate` | Cloud Vision プロキシ |
| POST | `/api/security/mask` | サーバー側 PII マスキング |

---

## ☁️ Cloudflare へのデプロイ

### 前提

- Workers プラン（Durable Objects は SQLite バックエンドのみのため無料プランでも利用可能）
- R2 バケット 2 本、Workers KV namespace 1 件

### 手順

```bash
cd manual-maker-workers
npm ci

# 1. R2 バケットを作成（存在しない場合）
npx wrangler r2 bucket create manual-processor-files
npx wrangler r2 bucket create manual-processor-files-secondary

# 2. KV namespace を作成し、出力された ID を wrangler.toml の PROCESSING_KV.id に反映する
npx wrangler kv namespace create PROCESSING_KV

# 3. API キーを secret として登録する
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put GOOGLE_API_KEY

# 4. デプロイ
npx wrangler deploy
```

`scheduled` ハンドラは毎日 UTC 02:00 に実行されます（`triggers.crons`）。

### 必要なバインディング

| バインディング | 種類 | 備考 |
|---|---|---|
| `BUCKET` | R2 | `manual-processor-files` |
| `BUCKET_SECONDARY` | R2 | 二重保存用。未設定でも動作する |
| `PROCESSING_KV` | KV | `wrangler.toml` の `id` はプレースホルダのまま。**必ず実 ID に置換すること** |
| `PROGRESS_DO` | Durable Object | `ProgressEngine`（SQLite バックエンド） |

### デプロイ前の検証

```bash
npm run typecheck   # tsc --noEmit
npm test            # vitest run（36 ファイル / 261 テスト）
npm run build       # wrangler deploy --dry-run
```

---

## 🆕 v3.2.0 新機能 & 変更点

- **Cloudflare Workers API クライアント抽象化 (v3.2)**
  - `src/lib/external-api.ts` に `GeminiApi` / `VisionApi` を集約。Gemini / Vision への呼び出しをサーキットブレーカー・リトライ・フォールバックキャッシュで統一的に処理する。
  - クライアントは isolate ごとに 1 つだけ生成し、リクエストごとに `env` を再バインドする。これによりサーキットブレーカーの状態がリクエスト間で維持される。
  - 認証情報が未設定の場合は上流を呼ばずに 502 を返す。
- **R2 バケット追加 & スケジューラー対応 (v3.2 新機能)**
  - `BUCKET_SECONDARY`（セカンダリ R2 バケット）を追加し、二重保存・バックアップ対応。
  - `triggers.crons = ["0 2 * * *"]` により、毎日午前2時からの定期タスク（クリーンアップ等）を有効化。
- **ルートコードの整理 & 型強化 (v3.2 新機能)**
  - `gemini.ts` / `vision.ts` から重複する API キー検証・リクエスト構築ロジックを抽出し、共通クライアントに集約。
  - `results.ts` / `security.ts` に `bodyLimit` ミドルウェアを追加し、リクエストボディサイズ制限を強化。
  - `security.ts` の型注釈を修正（同一の配列型表記を統一）。

---

## 🌟 主な機能 & アーキテクチャハイライト

- 🌐 **Web ベースのモダン操作画面 (FastAPI + Web UI)**
  - ドラッグ＆ドロップによる PDF アップロード、リアルタイム進捗表示、成果物プレビュー。
- ✏️ **フローチャート自動生成 & エディタ (Mermaid.js)**
  - AI による手順フローチャート自動生成および Mermaid.js リアルタイム編集。
- ⚡ **ハイブリッド AI プロセッサー & Map-Reduce 要約**
  - 新しい `google.genai` SDK と従来の `google.generativeai` の双方に対応。
  - 長文ドキュメントに対する **Map-Reduce 型の階層的要約**（各チャンクの要約＋全体統合要約）により高精度で一貫した要約を実現。
  - Gemini API トラブル時のローカルプロセッサーフォールバックメカニズム (`ProcessorFactory`)。
- 🔒 **セキュリティ & 個人情報自動マスキング**
  - 日本の電話番号・メールアドレス・郵便番号・クレジットカード番号・IPアドレス等の自動検出・マスキング (`SecurityManager`)。
- ⚙️ **セキュリティ戦略パターン & 依存性注入 (v3.0 新機能)**
  - `SecurityManager` が **依存性注入 (Dependency Injection)** に対応し、バックエンド戦略をランタイムで切り替え可能 (`SecurityConfig`)。
  - **ローカル環境**: ハードコードパターン / 環境変数キーストア / 暗号化無効戦略
  - **Cloudflare Workers環境**: KVストレージパターン / KVキーストア / Web Crypto API 暗号化
  - `create_workers_config()` によるワンクリック Workers 対応設定生成
  - ファイルシステム・keyring・cryptography ライブラリ非依存で Workers スタンドアロン実行可能
- 🌐 **Cloudflare Workers スタンドアロンデプロイ対応 (v3.0 新機能)**
  - `SecurityManager` が **Cloudflare Workers 環境でスタンドアロン動作** 可能に
  - KV Namespace (`PII_PATTERNS`, `API_KEYS`) と Secret (`ENCRYPTION_KEY`) のみで運用可能
  - `wrangler deploy` だけでデプロイ完了、追加インフラ不要
- 🚀 **性能最適化 & バッチ並列 OCR / キャッシュ管理**
  - メモリ (LRU Eviction) およびディスクベースの2層キャッシュ構造 (`CacheManager`)。
  - 大規模 PDF に対応した **バッチ並列 OCR & メモリ自動解放**（ページごとのリソース即時破棄）。
  - OCR 失敗ページのエラー状態トラッキング (`has_error`, `error_message`)。
- 📦 **マルチフォーマット出力 & ドキュメント生成**
  - 余白調整・絵文字挿入・コンパクトレイアウト対応の PDF / Word ドキュメント生成。
  - フローチャートは **Markdown (.md)** を標準出力し、**PNG** と **Mermaid (.mmd)** は設定で切替可能。エディタでの編集が容易。
  - Google Cloud TTS / edge-tts / gTTS による多層バックオフ音声合成。
- ✍️ **手書きPDFプロンプトエンジン**
  - 一字一句の書き起こし、判読不能文字、ルビ、ノイズ、縦書き・横書き、専門用語、図解、低品質画像に対応。
  - 日本語・英語・中国語のプロンプト、環境変数による追加ルール、メモリ・ディスクキャッシュに対応。

---

## 🎬 デモ & クイックスタート

### Web UI での処理フロー（推奨）

```bash
# 1. 依存関係インストール
pip install -r manual_processor/requirements.txt

# 2. 環境変数設定 (.env)
echo "GEMINI_API_KEY=your_api_key" > manual_processor/.env
echo "GOOGLE_API_KEY=your_api_key" >> manual_processor/.env

# 3. Web サーバー起動
cd manual_processor
python -m uvicorn src.web.app:app --reload --host 127.0.0.1 --port 8000
```

ブラウザで **http://localhost:8000** にアクセス

| ステップ | 操作 | 画面イメージ |
|----------|------|--------------|
| 1. アップロード | PDFをドラッグ＆ドロップ | 📤 ドロップゾーンにファイルを配置 |
| 2. オプション選択 | コンパクト/絵文字/厳格モード等 | ⚙️ チェックボックスで切替 |
| 3. AI処理実行 | 「AI パイプライン処理開始」クリック | ⚡ リアルタイム進捗バー表示 |
| 4. 結果確認 | タブで要約/フローチャート/ダウンロード | 📄📊💾 3タブで成果物確認 |
| 5. 編集・再生成 | Mermaidコード編集→プレビュー→保存 | ✏️ リアルタイムプレビュー更新 |

### CLI での単発処理

```bash
cd manual_processor

# 単一ファイル処理
python main.py --cli --input path/to/manual.pdf --output ./output

# バッチ処理（複数ファイル・ディレクトリ指定可）
python main.py --cli --input "file1.pdf,file2.pdf,./manuals/" --compact-layout --use-emojis

# ファイル監視モード（フォルダ監視・自動処理）
python main.py --cli
```

**出力例:**
```
--- 全 3 件のPDFファイルの処理を開始します ---
[1/3] 処理中: manual_001.pdf...
  ✅ 処理完了
    PDF: output/manual_001_formatted.pdf
    DOCX: output/manual_001.docx
    AUDIO: output/manual_001_audio.mp3
    DIAGRAM: output/diagram_abc123.md
[2/3] 処理中: manual_002.pdf...
  ✅ 処理完了
    ...
✅ バッチ処理終了: 3 / 3 件成功
```

### GUI モード（デスクトップアプリ）

```bash
cd manual_processor
python main.py          # GUI起動（デフォルト）
python main.py --gui    # 明示的指定
```

---

## 🏗️ フォルダ構成

```text
manual_processor/
├── config/                  # アプリケーション設定 (AppConfig シングルトン)
├── src/
│   ├── models.py            # 共通データモデル (Section等)
│   ├── exceptions.py        # カスタム例外クラス定義
│   ├── logger.py            # ロガー・例外ログ記録
│   ├── ocr_processor.py     # Vision API OCR プロセッサー
│   ├── gemini_ocr.py        # Gemini マルチモーダル OCR
│   ├── gemini_processor.py  # Gemini 要約・構造化・タイトル生成
│   ├── text_processor.py    # テキスト整形・クレンジング・キーワード抽出
│   ├── diagram_generator.py # Mermaid.js フローチャート生成 & レンダリング
│   ├── pdf_generator.py     # PDF 出力モジュール
│   ├── docx_generator.py    # Word 出力モジュール
│   ├── audio_generator.py   # 音声合成 (TTS) 出力モジュール
│   ├── output_manager.py    # 出力ファイル一括保存・管理
│   ├── orchestrator.py      # 全体処理ワークフロー＆非同期スレッド管理
│   ├── batch_processor.py   # バッチ処理＆優先度付きキュー管理
│   ├── usb_monitor.py       # USBドライブ監視・自動読み込み
│   ├── cache_manager.py     # LRU メモリ & ディスクキャッシュ
│   ├── security_manager.py  # PII マスキング
│   ├── progress_manager.py  # 進捗通知 & キャンセルトークン
│   ├── i18n_manager.py      # 多言語対応 (i18n)
│   ├── processor/           # プロセッサーファクトリー & ハイブリッド切り替え
│   ├── gui/                 # デスクトップ GUI モジュール
│   ├── web/                 # FastAPI Web UI バックエンド & フロントエンド
│   └── security/            # セキュリティ戦略パターン実装 (v3.0+)
│       ├── interfaces.py    # PatternProvider/KeyStore/EncryptionProvider プロトコル
│       ├── strategies.py    # ハードコード/環境変数/無効化戦略
│       ├── strategies_workers.py # Cloudflare Workers用戦略 (KV/Web Crypto)
│       └── config.py        # SecurityConfig DI 設定クラス
├── tests/                   # pytest テストスイート (1,332件)
├── scripts/                 # スタンドアロン exe ビルドスクリプト等
├── main.py                  # アプリケーション共通エントリーポイント
├── pyproject.toml           # パッケージメタデータ・依存関係
└── requirements.txt         # 依存ライブラリ一覧
```

---

## 💻 システム要件

- **OS**: Windows 10 / 11（Linux・macOS でも動作可能）
- **Python**: Python 3.8 以上 (Python 3.14 で動作検証済み)
- **メモリ**: 最小 4GB（推奨 8GB以上）
- **API Key**: [Google AI Studio](https://aistudio.google.com/) で取得した API キー
- **依存ライブラリ**: `requirements.txt` を参照

---

## 📦 インストール & 実行方法

### 1. 依存ライブラリのインストール
```bash
cd manual_processor
pip install -r requirements.txt
```

### 2. 環境変数の設定 (`.env`)
プロジェクトルート (`manual_processor/`) に `.env` ファイルを作成し、APIキー等を設定します：
```env
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_API_KEY=your_google_api_key_here

# 手書きPDFプロンプト設定（任意）
APP_LANGUAGE=ja
PROMPT_LAYOUT=horizontal
PROMPT_DOMAIN_TERMS=用語A,用語B
PROMPT_HAS_DIAGRAMS=False
PROMPT_LOW_QUALITY_MODE=False
PROMPT_STRICT_MODE=True
# 追加ルールは改行区切り
PROMPT_CUSTOM_RULES=
```

### 3. Web UI モードで起動（推奨）
```bash
python -m uvicorn src.web.app:app --reload --host 127.0.0.1 --port 8000
```
ブラウザで `http://localhost:8000` にアクセスしてください。

### 4. CLI / GUI モードで起動
```bash
# デスクトップ GUI モード
python main.py

# CLI モード（単一/バッチファイル指定）
python main.py --cli --input path/to/manual.pdf

# CLI ファイル監視モード
python main.py --cli
```

### 5. スタンドアロン `.exe` ファイルのビルド
```bash
python scripts/build_exe.py
```
ビルド完了後、`dist/ManualProcessor.exe` が生成されます。

---

## 🔒 セキュリティ & 個人情報自動マスキング (v3.0 強化)

- 日本の電話番号・メールアドレス・郵便番号・クレジットカード番号・IPアドレス等の自動検出・マスキング (`SecurityManager`)。

### SecurityManager 設定駆動アーキテクチャ (v3.0+)

v3.0 より `SecurityManager` は **依存性注入 (Dependency Injection)** に完全対応しました。`SecurityConfig` を通じてバックエンド戦略をランタイムで切り替え可能です。

#### 基本的な使用方法 (ローカル環境)

```python
from src.security.config import SecurityConfig
from src.security.strategies import HardcodedPatternProvider, EnvVarKeyStore, NoOpEncryption
from src.security_manager import SecurityManager

# カスタム設定を作成
config = SecurityConfig(
    pattern_provider=HardcodedPatternProvider(),  # ハードコード済みPIIパターン
    key_store=EnvVarKeyStore(),                    # 環境変数ベースのAPIキー保存
    encryption_provider=NoOpEncryption()           # 暗号化なし（開発・テスト用）
)

# SecurityManager で使用
masked, info = SecurityManager.mask_sensitive_data(
    "連絡先: test@example.com",
    config=config
)
print(masked)  # "連絡先: [REDACTED_EMAIL]"
print(info["counts"])  # {"EMAIL": 1}
```

#### Cloudflare Workers 環境での使用

```python
from src.security.config import SecurityConfig
from src.security.strategies_workers import create_workers_config
from src.security_manager import SecurityManager

# Workers環境用設定（KVストレージ自動検出）
config = create_workers_config()

# 通常通り使用
masked, info = SecurityManager.mask_sensitive_data(
    "連絡先: test@example.com",
    config=config
)
```

#### カスタムパターンプロバイダーの実装

```python
from src.security.interfaces import PatternProvider
from src.security.config import SecurityConfig
from src.security.strategies import EnvVarKeyStore, NoOpEncryption
from src.security_manager import SecurityManager

class CustomPatternProvider(PatternProvider):
    def load_patterns(self):
        return [
            ("CUSTOM_ID", r"ID-\d{6}", "[REDACTED_ID]"),
            ("INTERNAL_CODE", r"INT-[A-Z]{3}", "[REDACTED_CODE]"),
        ]

config = SecurityConfig(
    pattern_provider=CustomPatternProvider(),
    key_store=EnvVarKeyStore(),
    encryption_provider=NoOpEncryption()
)

masked, info = SecurityManager.mask_sensitive_data(
    "User ID-123456 with code INT-ABC",
    config=config
)
# "User [REDACTED_ID] with code [REDACTED_CODE]"
```

#### 後方互換性

既存コードは変更不要です。`config` パラメータを渡さない場合、従来の動作（YAML設定ファイル、keyring、環境変数ベースの暗号化）がそのまま維持されます。

```python
# 既存コード（変更なしで動作）
from src.security_manager import SecurityManager

masked, info = SecurityManager.mask_sensitive_data("Email: test@example.com")
# 従来通りYAMLパターンファイルから読み込み、keyringでAPIキー管理
```

#### Cloudflare Workers デプロイ手順

> ⚠️ **この節は Python 版の `SecurityManager` を Worker に移植する場合の手順であり、公開されている Worker の構成ではありません。**
> `manual-maker-workers/wrangler.toml` は `PII_PATTERNS` / `API_KEYS` バインディングを **定義していません**。
> 同梱の Worker は PII マスキングを `src/routes/security.ts` のサーバー側実装で行い、KV を経由しません。
> 迷った場合は、この README 先頭の「Cloudflare へのデプロイ」節を参照してください。

Python 側を Worker で運用する場合のみ、以下を追加します。

```toml
# manual_processor/wrangler.toml （別構成）
[[kv_namespaces]]
binding = "PII_PATTERNS"
id = "your-pii-patterns-kv-id"

[[kv_namespaces]]
binding = "API_KEYS"
id = "your-api-keys-kv-id"
```

```bash
# 暗号化キーの設定 (32バイトをBase64エンコード)
wrangler secret put ENCRYPTION_KEY

# デプロイ
wrangler deploy
```

---

## 🧪 テストの実行

### Workers (`manual-maker-workers/`)

```bash
cd manual-maker-workers
npm ci
npm run typecheck   # tsc --noEmit
npm test            # vitest run
```

**36 ファイル / 261 テスト**。外部 API は全てモック実行です。

### Python (`manual_processor/`)

```bash
cd manual_processor
pip install -e ".[dev]"
pytest tests/ -v
```

**1,332 テスト成功**（+ 16 skip）。外部 AI API は全てモック実行です。

カバレッジ付き実行：
```bash
pytest tests/ --cov=src --cov=config
```

---


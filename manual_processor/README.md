# 手書きマニュアル処理システム (Manual Processor) v3.0.0

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-win.svg)]()
[![Tests](https://img.shields.io/badge/tests-1325%20passed-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](https://codecov.io/)
[![Status](https://img.shields.io/badge/status-production%20ready-brightgreen.svg)]()

スキャンされた手書きマニュアル（PDF）を読み込み、**Google Gemini API** および **Google Cloud Vision API** を活用して高精度なOCR解析・初心者向けの要約および構造化を行い、**PDF**・**Word文書**・**音声ファイル(MP3/WAV)**・**フローチャート画像(PNG)** の複数フォーマットで自動出力するシステムです。

---

## 🌟 主な機能 & 建築ハイライト

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
+ ⚙️ **セキュリティ戦略パターン & 依存性注入 (v3.0 新機能)**
  - `SecurityManager` が **依存性注入 (Dependency Injection)** に対応し、バックエンド戦略をランタイムで切り替え可能 (`SecurityConfig`)。
  - **ローカル環境**: ハードコードパターン / 環境変数キーストア / 暗号化無効戦略
  - **Cloudflare Workers環境**: KVストレージパターン / KVキーストア / Web Crypto API 暗号化
  - `create_workers_config()` によるワンクリック Workers 対応設定生成
  - ファイルシステム・keyring・cryptography ライブラリ非依存で Workers スタンドアロン実行可能
+ 🌐 **Cloudflare Workers スタンドアロンデプロイ対応 (v3.0 新機能)**
  - `SecurityManager` が **Cloudflare Workers 環境でスタンドアロン動作** 可能に
  - KV Namespace (`PII_PATTERNS`, `API_KEYS`) と Secret (`ENCRYPTION_KEY`) のみで運用可能
  - `wrangler publish` だけでデプロイ完了、追加インフラ不要
- 🚀 **性能最適化 & バッチ並列 OCR / キャッシュ管理**
  - メモリ (LRU Eviction) およびディスクベースの2層キャッシュ構造 (`CacheManager`)。
  - 大規模 PDF に対応した **バッチ並列 OCR & メモリ自動解放**（ページごとのリソース即時破棄）。
  - OCR 失敗ページのエラー状態トラッキング (`has_error`, `error_message`)。
- 📦 **マルチフォーマット出力 & ドキュメント生成**
  - 余白調整・絵表情入・コンパクトレイアウト対応の PDF / Word ドキュメント生成。
  - フローチャートは **Markdown (.md)** を標準出力し、**PNG** と **Mermaid (.mmd)** は設定で切替可能。エディタでの編集が容易。
  - Google Cloud TTS / edge-tts / gTTS による多層バックオフ音声合成。
- ✍️ **手書きPDFプロンプトエンジン**
  - 一字一句の書き起こし、判読不能文字、ルビ、ノイズ、縦書き・横書き、専門用語、図解、低品質画像に対応。
  - 日本語・英語・中国語のプロンプト、環境変数による追加ルール、メモリ・ディスクキャッシュに対応。

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
├── tests/                   # pytest テストスイート (1325件)
├── scripts/                 # スタンドアロン exe ビルドスクリプト等
├── main.py                  # アプリケーション共通エントリーポイント
└── requirements.txt         # 依存ライブラリ一覧
```

---

## 💻 システム要件

- **OS**: Windows 10 / 11（Linux・macOS でも動作可能）
- **Python**: Python 3.8 以上 (Python 3.14 で動作検証済み)
- **メモリ**: 最小 4GB（推奨 8GB以上）
- **API Key**: [Google AI Studio](https://aistudio.google.com/) で取得した API キー
- **依存ライブラリ**: requirements.txt を参照

---

## 📦 インストール & 実行方法

### 1. 依存ライブラリのインストール
```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定 (`.env`)
プロジェクトルートに `.env` ファイルを作成し、APIキー等を設定します：
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

## 🔒 セキュリティ & 個人情報自動マスキング

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

```toml
# wrangler.toml
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
wrangler publish
```

---

## 🧪 テストの実行

全1325件のユニットテスト・統合テストを実行します：

```bash
python -m pytest tests/ -v
```

現在のテスト件数は1325件です。外部AI APIを使用するテストはモックで実行します。

---

## 📝 ライセンス

このプロジェクトは MIT ライセンスのもとで公開されています。
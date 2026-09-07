# Manual Processor

手書きマニュアルを AI で読み取り、要約・構造化・複数フォーマット出力へ自動変換するシステムです。

## ハイライト

- 🌐 **Web UI** — FastAPI ベース、ドラッグ&ドロップで PDF をアップロード
- 🤖 **ハイブリッド AI** — Gemini / Google Cloud Vision を用途別に切替
- 🔒 **PII マスキング** — 電話番号・メール・マイナンバー等を自動検出
- 📊 **観測性** — Prometheus `/metrics` でジョブ数・処理時間・エラーを可視化
- 📦 **マルチフォーマット出力** — PDF / Word / 音声(MP3) / フローチャート

## クイックスタート

```bash
pip install -r requirements.txt
cp .env.example .env   # GEMINI_API_KEY を設定
python -m uvicorn src.web.app:app --reload --port 8000
```

詳細は [Getting Started](getting-started.md) を参照してください。

## ステータス

| 指標 | 値 |
|------|---|
| テスト数 | 543 passed |
| カバレッジ | 67% (CIゲート 65%) |
| 対応 Python | 3.8 - 3.12 |
| ライセンス | MIT |
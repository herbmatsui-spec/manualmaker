# Getting Started

## 必要環境

- Python 3.8 以上
- 4 GB 以上のメモリ(8 GB 推奨)
- Google AI Studio の API キー

## インストール

```bash
git clone <repo>
cd manualmaker/manual_processor
pip install -r requirements.txt
pip install -e .[dev]    # 開発時は dev extras も
```

## 設定

`.env` をプロジェクトルートに作成します。

```env
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
```

## 起動モード

| モード | コマンド |
|--------|----------|
| Web UI | `python -m uvicorn src.web.app:app --reload` |
| CLI | `python main.py --cli --input path/to/manual.pdf` |
| デスクトップ GUI | `python main.py` |

## 次のステップ

- [Architecture](architecture.md) で内部構造を理解する
- [API Reference](api/index.md) で REST エンドポイントを確認する
- [Deployment](deployment.md) で本番運用の方針を確認する
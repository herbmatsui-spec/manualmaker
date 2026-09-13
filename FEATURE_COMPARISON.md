# 機能比較: 現行 Python版 vs Cloudflare Workers版 (案A: クライアントオフロード)

| 機能カテゴリ | 現行 Python版 (FastAPI) | Cloudflare Workers版 (案A) | 備考 |
|--------------|-------------------------|----------------------------|------|
| **ランタイム** | Python 3.8+ | V8/TypeScript (Cloudflare Workers) | Workersは10ms CPU制限あり |
| **Webフレームワーク** | FastAPI + Uvicorn | Hono on Cloudflare Workers | 軽量かつ高速 |
| **ファイルストレージ** | ローカルファイルシステム | Cloudflare R2 (S3互換) | 無料枠: 10GB保存、Class A/B操作無料 |
| **KVストレージ** | メモリ/ディスク (LRU) | Cloudflare KV | 無料枠: 10万読み/日、1000書き/日 |
| **キャッシュ** | LRU + ディスク2層 | Cloudflare KV (TTL設定可能) | 同様の無料枠 |
| **PDF処理** | PyMuPDF (サーバーサイド) | PDF.js (ブラウザサイド) + APIプロキシ | PDFテキスト抽出はブラウザで、残りはGemini APIへ |
| **OCR** | Google Cloud Vision API (Python SDK) | Google Cloud Vision API (REST) | APIキーはWorkersのSecretに保存 |
| **AI処理** | Gemini (Python SDK) | Gemini REST API | 同じAPIを呼び出すが、WorkersからFetch |
| **ドキュメント生成** | python-docx, fpdf2, pypdfium2 | ブラウザ側 (jsPDF, docx-generators) または API経由 | 案AではMarkdown出力に絞り、ブラウザで変換 |
| **音声合成** | edge-tts / gTTS | Web Speech API (ブラウザ) または 外部API | 無料枠内で可能な範囲に限定 |
| **フローチャート** | Mermaid.js (サーバーサイド生成) | Mermaid.js (ブラウザサイド) | 編集・プレビューはブラウザで完結 |
| **多言語対応** | Python i18n | i18n-js または JSONリソース | 翻訳データは静的ファイルまたはKV |
| **認証・認可** | カスタム (APIキー検証) | 同上 (Workersミドルウェア) | APIキーはSecret管理 |
| **レート制限** | ミドルウェア (memory) | Cloudflare KV ベース | エッジで高速に動作 |
| **WebSocket** | Native FastAPI WS | Durable Objects (有料) または polling | 案AではKVポーリングまたはSSEに変更 |
| **進捗表示** | WebSocket + Durable Objects | SSE (Server-Sent Events) または KVポーリング | 無料枠内で実装可能 |
| **静的ファイル配信** | Jinja2テンプレート | Cloudflare Pages (静的ホスティング) | ビルド不要で即時配信 |
| **デプロイ** | Docker / VM / ローカルPython | `wrangler publish` (Workers/Pages) | 無料枠内で完結 |
| **コスト** | サーバー維持費 | 無料枠内で $0 (条件付き) | Gemini/Vision APIの使用量による |
| **開発言語** | Python | TypeScript | 型安全かつモダン |
| **ビルドツール** | setuptools / pyinstaller | wrangler + typescript | 簡単なCI/CD |
| **テスト** | pytest | vitest / jest + wrangler vet | 同様のテスト可能 |
| **監視・ログ** | カスタムログ + OpenTelemetry | Cloudflare Logs + メトリクス | ダッシュボードで閲覧可能 |
| **制限事項** | なし (サーバー次第) | - CPU 10ms/リクエスト<br>- Workers Unboundは無料枠なし<br>- Python Workersは有料必須 | 案Aではこれらを回避する設計 |

## 案Aの核となる設計方針
1. **重い処理をクライアントまたは外部APIにオフロード**
   - PDFテキスト抽出: pdf.js (ブラウザ)
   - 要約・構造化: Gemini API (直接呼び出し)
   - ドキュメント生成: ブラウザ側ライブラリまたはAPI経由 (案AではMarkdown出力に絞る)
2. **WorkersはAPIゲートウェイと静的ホストに特化**
   - ファイルアップロード → R2
   - メタデータ管理 → KV
   - 外部API (Gemini/Vision) へのプロキシ (APIキー漏洩防止)
   - 進捗管理 → KVまたはSSE
3. **無料枠内での運用を前提**
   - r2storage: 10GBまで無料
   - kv: 読み込み枠に注意すれば無料
   - workers: 10万リクエスト/日無料
   - pages: 無料枠あり
   - gemini/vision: 無料枠あり (要確認)

## 機能削減の影響評価
| 削減・変更された機能 | 影響 | 代替案 |
|----------------------|------|--------|
| サーバーサイドPDF処理 (PyMuPDF) | PDFテキスト抽出がブラウザ側に移行 | pdf.js で代替可能 (精度はほぼ同等) |
| サーバーサイドOCR処理 | 画像OCRは Gemini API に依存 | Gemini API の無料枠内で実現可能 |
| サーバーサイドドキュメント生成 (PDF/DOCX) | 出力形式をMarkdownに限定 | ブラウザでMarkdown→PDF/DOCX変換ライブラリ利用可能 |
| サーバーサイド音声合成 | Web Speech API または 外部APIに依存 | ブラウザネイティブで対応可能 (言語制限あり) |
| WebSocketベースのリアルタイム進捗 | SSEまたはポーリングに変更 | ほぼ同等のUXを提供可能 |
| サーバーサイドMermaidレンダリング | ブラウザサイドに移行 | むしろ編集性が向上 |

## 結論
案A (クライアントオフロード) により、Cloudflare Workersの無料枠内で核となる機能を提供することが可能です。
ただし、以下の点に注意する必要があります:
1. Gemini APIおよびGoogle Cloud Vision APIの無料枠を超えるとコストが発生します。
2. ブラウザ側の処理能力に依存するため、古い端末では遅延が発生する可能性があります。
3. 機能は絞られますが、手書きマニュアル処理の基本的なワークフロー (アップロード→テキスト抽出→要約→構造化→出力)は維持できます。

次のステップとして、詳細な実装計画書を作成します。
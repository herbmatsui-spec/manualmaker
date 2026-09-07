# Cloudflare Workers 版実装計画書

## 概要

Python FastAPI バックエンドを Cloudflare Workers (TypeScript) へ移行し、Cloudflare Pages で静的ホストする構成。

## アーキテクチャ変更点

| コンポーネント | Python (旧) | TypeScript/Cloudflare (新) |
|--------------|-------------|---------------------------|
| ランタイム | Python 3.8+ | V8/TypeScript |
| Webフレームワーク | FastAPI | Cloudflare Workers |
| ファイル存储 | ローカルFS | R2 Object Storage |
| KV存储 | メモリ/Disk | Cloudflare KV |
| キャッシュ | LRU + Disk | Cloudflare KV |
| PDF処理 | PyMuPDF (ローカル) | PDF.js (ブラウザ) + API呼出 |
| OCR | Google Cloud Vision | Google Cloud Vision API |
| AI処理 | Gemini (Python SDK) | Gemini REST API |
| 音声合成 | edge-tts/gtts | Web Speech API / External API |
| 静的配信 | FastAPI + Jinja2 | Cloudflare Pages |

---

## フェーズ1: プロジェクト基盤 (ステップ 1-10)

### ステップ 1: Wrangler設定ファイル作成
- ファイル: `wrangler.toml`
- 設定内容:
  - `name`: "manual-processor"
  - `main`: "src/index.ts"
  - `compatibility_date`: "2024-01-01"
  - R2 binding: `BUCKET`
  - KV namespace binding: `PROCESSING_KV`
  - 環境変数バインディング設定

### ステップ 2: package.json 作成
- 依存関係:
  - `typescript` ^5.3.0
  - `wrangler` ^3.0.0
  - `@cloudflare/workers-types` ^4.20240117.0
  - `hono` ^4.0.0 (軽量Webフレームワーク)
  - `zod` ^3.22.0 (バリデーション)
  - `ai` ^2.0.0 (Gemini SDK)

### ステップ 3: tsconfig.json 作成
- `target`: "ES2022"
- `module`: "ESNext"
- `moduleResolution`: "bundler"
- `lib`: ["ES2022", "WebWorker"]
- `strict`: true
- `types`: ["@cloudflare/workers-types"]

### ステップ 4: ディレクトリ構造作成
```
manual-maker-workers/
├── src/
│   ├── index.ts              # エントリーポイント
│   ├── routes/
│   │   ├── health.ts         # /api/health
│   │   ├── config.ts         # /api/config
│   │   ├── upload.ts         # /api/upload
│   │   ├── process.ts        # /api/process/:fileId
│   │   ├── results.ts        # /api/results/:fileId
│   │   ├── download.ts      # /api/download/:fileId/:type
│   │   ├── i18n.ts          # /api/i18n/*
│   │   └── mermaid.ts        # /api/mermaid/*
│   ├── lib/
│   │   ├── storage.ts        # R2/KV 操作
│   │   ├── config.ts         # 設定管理
│   │   ├── types.ts          # 型定義
│   │   └── utils.ts          # ユーティリティ
│   ├── services/
│   │   ├── ocr.ts            # Google Cloud Vision API
│   │   ├── gemini.ts         # Gemini API
│   │   ├── pdf.ts            # PDF生成
│   │   ├── docx.ts           # DOCX生成
│   │   └── audio.ts          # 音声合成
│   └── i18n/
│       └── translations.ts   # 翻訳データ
├── static/                   # Cloudflare Pages用
│   ├── index.html
│   ├── js/app.js
│   └── css/style.css
├── wrangler.toml
├── package.json
├── tsconfig.json
└── .dev.vars                  # 開発用シークレット
```

### ステップ 5: 型定義ファイル作成 (src/lib/types.ts)
```typescript
interface Env {
  BUCKET: R2Bucket;
  PROCESSING_KV: KVNamespace;
  GEMINI_API_KEY: string;
  GOOGLE_API_KEY: string;
  GOOGLE_CLOUD_PROJECT_ID: string;
}

interface UploadedFile {
  fileId: string;
  filename: string;
  sizeMb: number;
  path: string;
  uploadedAt: string;
}

interface ProcessingResult {
  success: boolean;
  inputFile: string;
  title?: string;
  extractedText?: string;
  summary?: string;
  keyPoints?: string[];
  sections?: Section[];
  glossary?: GlossaryItem[];
  mermaidCode?: string;
  outputFiles?: OutputFiles;
  error?: string;
}

interface Section {
  title: string;
  content: string;
}

interface GlossaryItem {
  term: string;
  explanation: string;
}

interface OutputFiles {
  pdf?: string;
  docx?: string;
  audio?: string;
  diagram?: string;
}
```

### ステップ 6: Hono アプリ初期化 (src/index.ts)
```typescript
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { etag } from 'hono/etag';
import { logger } from 'hono/logger';

const app = new Hono<{ Bindings: Env }>();

app.use('*', cors());
app.use('*', etag());
app.use('*', logger());

export default app;
```

### ステップ 7: wrangler.toml R2/KV設定
```toml
name = "manual-processor"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[[r2_buckets]]
binding = "BUCKET"
bucket_name = "manual-processor-files"

[[kv_namespaces]]
binding = "PROCESSING_KV"
id = "your-kv-namespace-id"

[vars]
DEFAULT_LANGUAGE = "ja"
MAX_FILE_SIZE_MB = "50"
WEB_UPLOAD_MAX_MB = "100"
```

### ステップ 8: 開発用.env (.dev.vars)
```
GEMINI_API_KEY=your_gemini_key
GOOGLE_API_KEY=your_google_key
GOOGLE_CLOUD_PROJECT_ID=your_project_id
DEFAULT_LANGUAGE=ja
MAX_FILE_SIZE_MB=50
WEB_UPLOAD_MAX_MB=100
```

### ステップ 9: 型定義の補充 (steps 1-8で不足分)
- `ProcessOptions` インターフェース追加
- `SetLanguageRequest` インターフェース追加
- `MermaidRenderRequest` インターフェース追加
- `MermaidRegenerateRequest` インターフェース追加
- レスポンス型の全て定義

### ステップ 10: ベースURL/ルート設定確認
- `app.basePath` = "/api" (API routes prefixed)
- 全エンドポイントPATH確認
- HTTPメソッド確認 (GET/POST/WebSocket)

---

## フェーズ2: 基本APIエンドポイント (ステップ 11-25)

### ステップ 11: /api/health エンドポイント実装
```typescript
app.get('/api/health', (c) => {
  return c.json({
    status: 'ok',
    version: '2.0.0',
    processorType: 'cloudflare-workers'
  });
});
```

### ステップ 12: /api/config エンドポイント実装
- `geminiModelName` 取得
- `processorType` 取得
- `pdfDpi` 取得
- `maxFileSizeMb` 取得
- `webUploadMaxMb` 取得
- `supportedExtensions` 取得
- `defaultLanguage` 取得

### ステップ 13: /api/i18n/languages エンドポイント実装
- 利用可能言語リストを返す
- 対応言語: ja, en, zh, ko, es

### ステップ 14: /api/i18n/set エンドポイント実装
- POST body: `{ language: string }`
- 言語設定更新 (KVに保存)

### ステップ 15: /api/i18n/translations/:lang エンドポイント実装
- 指定言語の翻訳オブジェクトを返す
- 存在しない場合は404

### ステップ 16: /api/i18n/detect エンドポイント実装
- POST body: `{ text: string }`
- 言語自動検出 (Unicode範囲ベース)
  - 日本語: ひらがな/カタカナ検出
  - 中国語: 漢字範囲
  - 韓国語: ハングル範囲
  - スペイン語: アクセント文字

### ステップ 17: /api/security/status エンドポイント実装
- PIIマスキング有効可否
- 暗号化可否
- 監査ログ有効可否

### ステップ 18: /api/security/audit エンドポイント実装
- 監査ログ取得 (KVから)
- limit パラメータ対応

### ステップ 19: /api/security/mask エンドポイント実装
- POST body: `{ text: string }`
- 機密情報マスキング:
  - メールアドレス
  - 電話番号 (日本)
  - マイナンバー
  - パスポート番号
  - 郵便番号
  - クレジットカード番号
  - IPアドレス
  - 銀行口座

### ステップ 20: パス変数バリデーション共通関数
```typescript
function validateFileId(fileId: string): boolean {
  return /^[a-f0-9]{32}$/.test(fileId);
}
```

### ステップ 21: /api/upload POST エンドポイント実装 (前半)
- Content-Type: multipart/form-data
- PDFのみ許可 (.pdf 拡張子チェック)
- ファイルサイズ上限チェック (config.webUploadMaxMb)

### ステップ 22: /api/upload POST エンドポイント実装 (後半)
- UUID生成 (fileId)
- R2バケットにファイル保存
- メタデータをKVに保存
- レスポンス: `{ fileId, filename, sizeMb, path }`

### ステップ 23: /api/uploads GET エンドポイント実装
- 全アップロード済みファイル一覧取得
- KVからメタデータ読み込み

### ステップ 24: /api/results/:fileId GET エンドポイント実装
- KVから処理結果取得
- 存在しない場合は404
- fileIdバリデーション

### ステップ 25: /api/download/:fileId/:type GET エンドポイント実装
- type: pdf | docx | audio | diagram
- R2バケットからファイル取得
- Content-Disposition ヘッダー設定
- Content-Type 適切に設定

---

## フェーズ3: ストレージ抽象化レイヤー (ステップ 26-35)

### ステップ 26: R2操作基底クラス作成 (src/lib/storage.ts)
```typescript
export class R2Storage {
  constructor(private bucket: R2Bucket) {}

  async upload(key: string, data: ArrayBuffer, contentType: string): Promise<void> {
    await this.bucket.put(key, data, {
      httpMetadata: { contentType }
    });
  }

  async download(key: string): Promise<R2Object | null> {
    return await this.bucket.get(key);
  }

  async delete(key: string): Promise<void> {
    await this.bucket.delete(key);
  }

  async list(prefix: string): Promise<R2Objects> {
    return await this.bucket.list({ prefix });
  }
}
```

### ステップ 27: KV操作基底クラス作成
```typescript
export class KVStorage {
  constructor(private kv: KVNamespace) {}

  async get<T>(key: string): Promise<T | null> {
    const value = await this.kv.get(key, 'json');
    return value as T | null;
  }

  async put<T>(key: string, value: T, expirationTtl?: number): Promise<void> {
    await this.kv.put(key, JSON.stringify(value), {
      expirationTtl
    });
  }

  async delete(key: string): Promise<void> {
    await this.kv.delete(key);
  }

  async list(prefix: string): Promise<string[]> {
    const list = await this.kv.list({ prefix });
    return list.keys.map(k => k.name);
  }
}
```

### ステップ 28: ファイルメタデータ保存関数
```typescript
const UPLOADED_FILES_PREFIX = 'uploaded:';

async function saveFileMetadata(fileId: string, meta: UploadedFile): Promise<void> {
  // KVにメタデータ保存
}
```

### ステップ 29: 処理結果保存関数
```typescript
const RESULTS_PREFIX = 'result:';

async function saveProcessingResult(fileId: string, result: ProcessingResult): Promise<void> {
  // 結果オブジェクトをJSONシリアライズしてKV保存
  // 有効期限: 24時間
}
```

### ステップ 30: 進捗状態保存関数
```typescript
const PROGRESS_PREFIX = 'progress:';

interface ProgressUpdate {
  status: string;
  progress: number;
  stage: string;
  message?: string;
}

async function saveProgress(fileId: string, update: ProgressUpdate): Promise<void> {
  // WebSocketクライアントへの通知も実施
}
```

### ステップ 31: R2キー命名規則定義
```
uploads/{fileId}/{filename}     # 元ファイル
results/{fileId}/output.pdf     # 生成PDF
results/{fileId}/output.docx   # 生成DOCX
results/{fileId}/output.mp3     # 生成音声
results/{fileId}/output.png     # 生成ダイアグラム
```

### ステップ 32: ファイル存在チェック関数
```typescript
async function fileExists(key: string): Promise<boolean> {
  const obj = await bucket.head(key);
  return obj !== null;
}
```

### ステップ 33: 一時的アップロードauri清理関数
```typescript
async function cleanupUpload(fileId: string): Promise<void> {
  // 24時間以上古いアップロードを削除
}
```

### ステップ 34: 的大型ファイル分割アップロード対応
- Cloudflare Workers 100KB制限対応
- 100KB以上のファイルはチャンク分割
- チャンクのマージ処理実装

### ステップ 35: ストレージ抽象化レイヤー 完成
- `StorageService` クラスとして統合
- R2とKVの統一インターフェース提供

---

## フェーズ4: i18n (国際化) 実装 (ステップ 36-40)

### ステップ 36: 翻訳データ定義 (src/i18n/translations.ts)
```typescript
export const translations: Record<string, Record<string, string>> = {
  ja: {
    appTitle: '手書きマニュアル自動整理システム',
    summaryTitle: 'マニュアル概要',
    keyPointsTitle: '重要ポイント',
    // ... 25キー
  },
  en: { /* 英語 */ },
  zh: { /* 中国語 */ },
  ko: { /* 韓国語 */ },
  es: { /* スペイン語 */ }
};
```

### ステップ 37: 翻訳取得関数
```typescript
export function t(key: string, lang: string): string {
  return translations[lang]?.[key] ?? translations['ja'][key] ?? key;
}
```

### ステップ 38: 言語検出関数
```typescript
export function detectLanguage(text: string): string {
  // Unicode範囲ベースで言語判定
  // 0.05閾値で判定
}
```

### ステップ 39: 利用可能言語一覧取得
```typescript
export function getAvailableLanguages(): string[] {
  return Object.keys(translations);
}
```

### ステップ 40: サーバーサイド言語設定保存
- KVにユーザーごとの言語設定を保存
- expirationTtl: 30日間

---

## フェーズ5: PDF処理パイプライン (ステップ 41-50)

### ステップ 41: PDF光学認識 (OCR) サービス設計
```
PDF → (ブラウザJS) → 画像変換 → API送信 → Google Cloud Vision → テキスト
```

### ステップ 42: Google Cloud Vision API 呼び出し関数
```typescript
interface VisionOCRRequest {
  requests: [{
    image: { content: string }; // Base64エンコード
    features: [{ type: 'DOCUMENT_TEXT_DETECTION' }]
  }]
}

async function callVisionAPI(imageBase64: string): Promise<string> {
  // POST https://vision.googleapis.com/v1/images:annotate
  // Authorization: Bearer {GOOGLE_API_KEY}
}
```

### ステップ 43: Gemini OCR 代替関数
```typescript
async function callGeminiOCR(imageBase64: string, prompt: string): Promise<string> {
  // POST https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent
}
```

### ステップ 44: /api/process/:fileId POST エンドポイント実装 (前半)
- 入力検証: fileId存在チェック
- ファイルサイズチェック
- ファイル形式チェック

### ステップ 45: /api/process/:fileId POST エンドポイント実装 (中半)
- PDFダウンロード (R2から)
- 進捗更新: stage="ocr", progress=15

### ステップ 46: /api/process/:fileId POST エンドポイント実装 (後半)
- OCR処理実行
- テキスト抽出結果保存
- 進捗更新: stage="summarize", progress=50

### ステップ 47: Gemini 要約処理サービス
```typescript
interface SummarizeRequest {
  extractedText: string;
  modelName: string;
}

interface SummarizeResponse {
  title: string;
  summary: string;
  keyPoints: string[];
  sections: Section[];
  glossary: GlossaryItem[];
}
```

### ステップ 48: /api/process 完了処理
- 進捗更新: stage="output", progress=75
- 出力ファイル生成 (PDF/DOCX/音声/ダイアグラム)
- 進捗更新: stage="completed", progress=100
- 結果保存 (KV)

### ステップ 49: 処理オプション対応
```typescript
interface ProcessOptions {
  compactLayout: boolean;
  useEmojis: boolean;
  promptLayout: 'horizontal' | 'vertical';
  promptStrictMode?: boolean;
  promptHasDiagrams?: boolean;
  promptLowQualityMode?: boolean;
}
```

### ステップ 50: エラーハンドリング実装
- try-catch 全処理に包む
- 進捗エラー状態保存
- 詳細なエラーメッセージをKVに保存

---

## フェーズ6: 出力ファイル生成 (ステップ 51-60)

### ステップ 51: PDF生成サービス設計
```
、要約データ + Mermaid画像 → PDF生成API呼び出し
```

### ステップ 52: PDF生成REST API統合
```typescript
// 外部PDF生成APIを使用 (例: docraptor, pdfmyurl)
// または jspdf + jsPDF for browser-side PDF generation
```

### ステップ 53: DOCX生成サービス設計
```
Web Assembly版docx生成ライブラリ使用
または外部API
```

### ステップ 54: DOCX生成実装
```typescript
// @types/jszip + docx npm パッケージ (ブラウザ向け)
// または Cloudflare Workers上での制約を考量した代替案
```

### ステップ 55: Mermaidダイアグラム生成
```typescript
// Mermaid.js ライブラリをブラウザ側で実行
// または外部レンダリングAPI使用
```

### ステップ 56: /api/mermaid/validate エンドポイント
```typescript
app.post('/api/mermaid/validate', async (c) => {
  const { mermaidCode } = await c.req.json();
  const isValid = validateMermaidSyntax(mermaidCode);
  return c.json({ valid: isValid });
});
```

### ステップ 57: /api/mermaid/render エンドポイント
```typescript
// MermaidコードからPNG生成
// ブラウザ側でのレンダリングを返す
```

### ステップ 58: /api/mermaid/regenerate エンドポイント
- Gemini API呼び出し
- 自然言語指示からMermaidコード再生成

### ステップ 59: /api/mermaid/save/:fileId エンドポイント
- 編集したMermaidコードを保存
- PDF/DOCX 再生成

### ステップ 60: 出力ファイルR2保存
```typescript
async function saveOutputFile(fileId: string, type: string, data: ArrayBuffer): Promise<string> {
  const key = `results/${fileId}/output.${type}`;
  await r2Storage.upload(key, data, getContentType(type));
  return key;
}
```

---

## フェーズ7: WebSocket 進捗通知 (ステップ 61-65)

### ステップ 61: Durable Objects 設定 (wrangler.toml)
```toml
[durable_objects]
bindings = [{ name = "PROGRESS_DO", class_name = "ProgressEngine" }]
```

### ステップ 62: Durable Objects クラス定義
```typescript
export class ProgressEngine {
  private sessions: Map<number, WebSocket>;

  constructor(state: DurableObjectState) {
    this.state = state;
  }

  async fetch(request: Request): Promise<Response> {
    // WebSocket接続を確立
  }

  async webSocketMessage(ws: WebSocket, message: string): void {
    // クライアントからのping/pong処理
  }
}
```

### ステップ 63: /ws/progress/:fileId WebSocket ハンドラー
```typescript
// Durable Objects に接続
// リアルタイム進捗推送
```

### ステップ 64: 進捗更新関数
```typescript
async function updateProgress(fileId: string, progress: number, stage: string, message?: string): Promise<void> {
  // Durable Objects に通知
  // KV にもバックアップ保存
}
```

### ステップ 65: 接続切断処理
- WebSocket切断時のクリーンアップ
- セッション管理

---

## フェーズ8: フロントエンド静的ファイル (ステップ 66-72)

### ステップ 66: index.html 確認と調整
- 既存のHTMLをCloudflare Pages対応に調整
- APIベースURL変更
- CORS設定確認

### ステップ 67: app.js API呼び出し更新
```javascript
const API_BASE = '/api';  // Cloudflare Workers

async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData });
  return response.json();
}
```

### ステップ 68: WebSocket クライアント実装
```javascript
function connectProgress(fileId) {
  const ws = new WebSocket(`wss://${location.host}/ws/progress/${fileId}`);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateProgressUI(data.progress, data.stage);
  };
  return ws;
}
```

### ステップ 69: CORS 設定確認
```typescript
app.use('*', cors({
  origin: '*',  // 本番環境では制限
  allowMethods: ['GET', 'POST', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'Authorization']
}));
```

### ステップ 70: スタイルシート確認
- style.css の内容確認
- 必要な調整があればメモ

### ステップ 71: ブラウザ側PDF処理
```javascript
// PDF.js でPDFを画像に変換
// 画像Base64エンコード
// OCR API呼び出し
```

### ステップ 72: 最終結合テスト
- 全エンドポイント手動テスト
- CORS問題確認
- ファイルアップロード/ダウンロード確認
- 処理パイプライン確認
- WebSocket接続確認

---

## 技術的制約と対策

| 制約 | Cloudflare Workers | 対策 |
|------|-------------------|------|
| 実行時間 | 30秒 (CPU 10秒) | 非同期処理、外部API活用 |
| メモリ | 128MB | ファイルサイズ制限 (50MB) |
| バンドルサイズ | 1MB | 不要コード削除、圧縮 |
| Python不可 | V8のみ | 全てTypeScript/JS再実装 |
| ersistent接続 | WebSocket制限 | Durable Objects使用 |

## 依存サービス

| サービス | 用途 | 費用 |
|---------|------|------|
| Cloudflare Workers | ランタイム | Free (10万リクエスト/日) |
| Cloudflare R2 | ファイル存储 | 最初の10GB無料 |
| Cloudflare KV | メタデータ | 最初の10万読み取り無料 |
| Cloudflare Pages | 静的配信 | Free |
| Google Cloud Vision | OCR | 有料 (利用量ベース) |
| Gemini API | AI処理 | 有料 (利用量ベース) |

## 次世代拡張案

1. **Cloudflare D1** (SQLite) で永続データ存储
2. **Cloudflare Queues** でバックグラウンド処理
3. **Cloudflare Images** で画像最適化
4. **Cloudflare Email** で通知機能

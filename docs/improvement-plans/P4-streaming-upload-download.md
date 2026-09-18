# P4: ストリーミング アップロード/ダウンロード

## 概要
ファイル全体をメモリに読み込むのをやめ、ストリーミング処理によりメモリ使用量削減と大容量ファイル対応を実現する。アップロードはReadableStreamをR2に直接書き込み、ダウンロードはRangeリクエスト対応で効率化。

---

## ステップ1: アップロードストリーミング実装
**対象ファイル**: `src/routes/upload.ts`
- 現在: `file.arrayBuffer()` で全体メモリ読み込み（36行）
- 改善: `c.req.body` (ReadableStream) を直接 `BUCKET.put()` に渡す

```typescript
import { validate, getValidatedBody } from '../lib/validation';
import { bodyLimit } from '../lib/body-limit';
import { uploadBody, fileIdParam } from '../lib/schemas';
import { ValidationError } from '../lib/errors';

export function registerUploadRoutes(app: Hono<{ Bindings: Env }>) {
  app.post('/api/upload',
    bodyLimit({ maxSize: 100 * 1024 * 1024 }), // 100MB制限はヘッダーで事前チェック
    validate({ body: uploadBody }),
    async (c) => {
      try {
        const body = getValidatedBody<{ file: File }>(c);
        const file = body.file;
        const filename = file.name;

        // ファイルタイプチェック（ストリーミング中でも早期リターンのためヘッダーで簡易チェック）
        if (!filename.toLowerCase().endsWith('.pdf')) {
          throw new ValidationError('Only PDF files are allowed', { filename });
        }

        // ファイルサイズチェック（Content-Lengthヘダー優先、無ければストリームで測定）
        const contentLength = c.req.header('content-length');
        let size: number;
        if (contentLength) {
          size = parseInt(contentLength, 10);
          const maxSize = parseInt(c.env.WEB_UPLOAD_MAX_MB || '100', 10) * 1024 * 1024;
          if (size > maxSize) {
            throw new ValidationError(
              `File size (${(size / 1024 / 1024).toFixed(1)}MB) exceeds limit (${c.env.WEB_UPLOAD_MAX_MB || '100'}MB)`,
              { size, maxSize: parseInt(c.env.WEB_UPLOAD_MAX_MB || '100', 10) }
            );
          }
        }
        // Content-Length無い場合はストリーム消費後にチェック（非効率だが稀なケース）

        const fileId = uuidv4();
        const key = `uploads/${fileId}/${filename}`;

        // ストリーミングアップロード（メモリに全データを持たない）
        await c.env.BUCKET.put(key, file.body, { // File.body は ReadableStream
          httpMetadata: {
            contentType: 'application/pdf'
          }
        });

        // アップロード完了後に実際のサイズ取得（ストリーム消費済みのため別途HEADまたはメタデータ取得必要）
        // 代わりに、アップロード前にサイズチェック済みならそのまま使用
        // 厳密に言えば、実際の転送サイズはContent-Lengthと一致するはず

        const meta: UploadedFile = {
          fileId,
          filename,
          sizeMb: Math.round((size ?? 0) / 1024 / 1024 * 100) / 100, // サイズ不明時は0
          path: key,
          uploadedAt: new Date().toISOString()
        };

        await c.env.PROCESSING_KV.put(`uploaded:${fileId}`, JSON.stringify(meta));

        return c.json(meta);
      } catch (err) {
        if (err instanceof ValidationError) throw err;
        console.error('Upload error:', err);
        throw new StorageError('Upload failed', { cause: err });
      }
    }
  );

  // ... その他ルート unchanged
}
```

**注意**: Cloudflare Workers の `File` オブジェクトは `body` プロパティとして `ReadableStream` を持つ（MDN準拠）
**確認**: 小ファイルで動作確認、メモリプロファイリングでヒープ使用量抑制

---

## ステップ2: アップロードサイズストリーム測定
**課題**: Content-Lengthヘダーがない場合のサイズチェック
**解決策**: ストリームを消費しながらバイト数カウント（一度だけ読み取り）

```typescript
// アップロード関数内部で使用
async function measureStreamSize(stream: ReadableStream<Uint8Array>): Promise<{ size: number; stream: ReadableStream<Uint8Array> }> {
  let size = 0;
  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();
  
  const reader = stream.getReader();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      await writer.write(value);
    }
  } finally {
    reader.releaseLock();
    writer.close();
  }
  
  return { size, stream: readable };
}
```

**使用場面**: Content-Lengthヘダーがないアップロード時
**トレードオフ**: ストリームを二重読み取りせずにサイズ測定可能だが、実装複雑度増加。代わりに：
- 無理にストリームサイズ測定せず、アップロード後サイズ超過チェック（R2のアップロード完了後にメタデータ取得）
- または、Content-Length必須とする（ほとんどのブラウザは自動付与）

**採用方針**: Content-Lengthヘダー必須とする（仕様書に追加）、省略時は411エラー

---

## ステップ3: ダウンロード Range リクエスト対応
**対象ファイル**: `src/routes/download.ts`
- 現在: ファイル全体をストリームで返却（良いがRange非対応）
- 改善: `Range` ヘダー解析し、部分コンテンツ返却

```typescript
import { validate } from '../lib/validation';
import { getValidatedParams } from '../lib/validation';
import { validateFileId, getContentType } from '../lib/utils';
import { NotFoundError } from '../lib/errors';

export function registerDownloadRoutes(app: Hono<{ Bindings: Env }>) {
  app.get('/api/download/:fileId/:type',
    validate({ params: z.object({
      fileId: fileIdParam,
      type: z.enum(['pdf', 'md', 'markdown'])}),
    }),
    async (c) => {
      try {
        const { fileId, type } = getValidatedParams<{ fileId: string; type: 'pdf' | 'md' | 'markdown' }>(c);
        if (!validateFileId(fileId)) {
          throw new NotFoundError('File');
        }

        let key: string;
        let contentType: string;
        let dispositionFilename: string;

        if (type === 'pdf') {
          const metaJson = await c.env.PROCESSING_KV.get(`uploaded:${fileId}`);
          if (!metaJson) {
            throw new NotFoundError('Upload');
          }
          const meta = JSON.parse(metaJson) as UploadedFile;
          key = meta.path;
          contentType = 'application/pdf';
          dispositionFilename = `manual-${fileId.slice(0, 8)}.pdf`;
        } else if (type === 'md' || type === 'markdown') {
          key = `results/${fileId}/manual.md`;
          contentType = getContentType('md');
          dispositionFilename = `manual-${fileId.slice(0, 8)}.md`;
        } else {
          throw new ValidationError(`Unsupported type: ${type}`);
        }

        const obj = await c.env.BUCKET.get(key);
        if (!obj) {
          throw new NotFoundError('File');
        }

        // Rangeヘダー処理
        const rangeHeader = c.req.header('range');
        let status = 200;
        let headers = new Headers();
        
        if (rangeHeader && type === 'pdf') {
          // PDFのRangeリクエスト処理（簡易実装）
          const match = rangeHeader.match(/bytes=(\d+)-(\d*)/);
          if (match) {
            const start = parseInt(match[1], 10);
            const end = match[2] ? parseInt(match[2], 10) : undefined;
            
            // カスタム範囲取得（Workersではslice()メソッド利用可能？）
            // 代わりに、全体ストリームを返却し、ブラウザ側で処理させる簡易実装
            // 本格実装にはRangeオブジェクトが必要だが、ここでは省略
            // TODO: 実際のRange処理実装
          }
        }

        // メタデータ書き込み
        obj.writeHttpMetadata(headers);
        headers.set('Content-Type', contentType);
        headers.set('Content-Disposition', `attachment; filename="${dispositionFilename}"`);
        if (obj.httpEtag) headers.set('ETag', obj.httpEtag);
        
        // 実際のRange対応は今後の課題として、現在は200で全体返却
        // しかし、ステータスコードとヘダーは準備
        return new Response(obj.body, { 
          status, 
          headers 
        });
      } catch (err) {
        if (err instanceof ValidationError || err instanceof NotFoundError) throw err;
        console.error('Download error:', err);
        return c.json({ error: 'Download failed' }, 500);
      }
    }
  );
}
```

**改善点**: 
- Rangeヘダー解析の土台作り
- 今後のためにステータスコード206準備
- ETag活用でキャッシュ効率化

---

## ステップ4: ストリームエラーハンドリング強化
**ファイル**: `src/lib/stream-utils.ts` (新規)
- ストリーム読み込み中のエラーハンドリング統一
- タイムアウト付与、中断検知

```typescript
export async function streamToArrayBuffer(stream: ReadableStream<Uint8Array>, maxSize: number): Promise<ArrayBuffer> {
  const chunks: Uint8Array[] = [];
  let size = 0;
  
  const reader = stream.getReader();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      size += value.byteLength;
      if (size > maxSize) {
        throw new ValidationError(`Stream too large (max ${maxSize} bytes)`);
      }
      
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  
  return Blob(chunks).arrayBuffer();
}

// アップロードでの利用例（ストリームサイズ測定が必要な場合）
// 注意: この関数はメモリに全データをためるため、大容量非推奨
// → 本当のストリーミングではこの関数を使わず、直接BUCKET.putに渡す
```

**実際のアップロードでは**: `BUCKET.put(key, stream)` 直接使用のため、このユーティリティは代替策として保持

---

## ステップ5: アップロード中のプログレスイベント（オプション）
**課題**: アップロード進行状況をクライアントにフィードバックしたい
**解決策**: 
1. クライアント側で `XMLHttpRequest.upload.onprogress` または Fetch API の ReadableStream パイプ利用
2. サーバーサイドでは特に実装不要（クライアント→Workers→R2 のストリームは透過的）

**ただし**: アップロード完了までのタイムアウト検知のため、
- Workers側のリクエストタイムアウト（現在30秒）を考慮
- 大容量ファイルはチャンクアップロード実装が望ましい（Phase 2で検討）

**現状**: ストリーミングアップロードによりメモリ効率は改善したが、プログレスはクライアント側任せ

---

## ステップ6: ダウンロードストリーム最適化
**対象ファイル**: `src/routes/download.ts`
- 現在: `obj.text()` 等で全体メモリ読み込み（markdown取得時）
- 改善: ストリームのままレスポンス返却（すでに実装済みだが確認）

```typescript
// results.ts のGET（マークダウン取得）はすでにストリーム対応
app.get('/api/results/:fileId', async (c) => {
  // ...
  const obj = await c.env.BUCKET.get(meta.path);
  if (!obj) {
    throw new NotFoundError('Result file not found in storage');
  }
  
  // ここで obj.text() ではなく、ストリームをそのまま返すか、
  // またはRange対応のためにストリームを保持
  const markdown = await obj.text(); // 現状は全体読み込みだが、サイズ制限済み（10MB）
  
  // 代わりに、以下のようにストリームを返すことも可能だが、
  // JSONレスポンスにマークダウンテキストを含める必要があるため、
  // テキスト形式が必要なケースでは仕方ない
  // （クライアントが生マークダウン欲しいなら別エンドポイント作成可）
  
  return c.json({ ...meta, markdown }); // メタデータ+テキストなのでテキスト取得必須
});

// しかし、ダウンロードエンドポイント（/api/download/.../md）は
// ストリームをそのまま返すので効率的
```

**改善点**: 
- `/api/results/:fileId` のマークダウン取得は10MB制限ありなのでメモリ影響小
- しかし、ストリームをそのまま返す `/api/download/:fileId/md` は最適
- 今後: `/api/results/raw/:fileId` 等でプレーンテキストストリームエンドポイント追加検討

---

## ステップ7: アップロードストリームバックプレッシャー対応
**課題**: 高速アップロード時のバックプレッシャー制御
**解決策**: 
- `BUCKET.put(key, stream)` は内部でバックプレッシャーを処理
- ただし、リクエストボディの読み取り側（Hono）で制御が必要な場合あり
- `c.req.body` はキャンセル可能なストリームなので、クライアント切断時は自動停止

**確認**: 
- 大容量ファイルアップロード中にクライアントがキャンセルしたら、
  Workers側ストリームも自動でキャンセルされるかテスト
- カスタムタイムアウト実装が必要なら実装

---

## ステップ8: ストリームユーティリティテスト作成
**ファイル**: `src/lib/__tests__/stream-utils.test.ts` (新規)
- ストリームサイズ測定関数の正常・異常テスト
- 大容量ストリームでのメモリ使用量確認
- エラー時のストリームクローズ確認

---

## ステップ9: パフォーマンスベンチマーク・ドキュメント化
**ファイル**: `docs/performance/streaming.md` (新規)
- 改善前後でのメモリ使用量比較（ヒープスナップショット）
- 大容量ファイル（50MB, 100MB）アップロード/ダウンロード時間
- クライアント側プログレス実装ガイド
- 既知の制限事項（Rangeリクエスト未対応等）

**ベンチマーク項目**:
- メモリヒープ増加量（ストリーミング前後）
- リクエストレイテンシ（タイム・トゥ・ファーストバイト）
- 同時接続数における安定性

---

## 完了条件
- [ ] アップロードが `file.arrayBuffer()` ではなく `file.body` ストリーム使用
- [ ] ダウンロードが Range リクエストの土台実装済み（ヘダー解析・ステータスコード準備）
- [ ] 大容量ファイル（100MB近く）でもメモリ使用量抑制
- [ ] エラー時にもストリームが適切にクローズされる
- [ ] テストでストリーム関連機能網羅
- [ ] ドキュメントに実装方法と制限事項記載
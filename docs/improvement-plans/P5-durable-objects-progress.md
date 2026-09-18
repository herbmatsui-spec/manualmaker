# P5: Durable Objectsで進捗管理（KVポーリング置換）

## 概要
KVポーリングによる進捗取得をDurable Objectsに置き換え、リアルタイム進捗更新と無料枠消費削減を実現する。WebSocketまたはServer-Sent Events (SSE) を使用してクライアントにプッシュ通知。

---

## ステップ1: Durable Objects 有効化確認
**ファイル**: `wrangler.toml`
- 既に `[durable_objects]` セクションが存在（19-20行）
- `bindings = [{ name = "PROGRESS_DO", class_name = "ProgressEngine" }]`
- `compatibility_date` が適切か確認（`2024-01-01` 以上推奨）

**確認**: `wrangler deploy --dry-run` で設定エラーなし

---

## ステップ2: ProgressEngine クラス実装
**ファイル**: `src/lib/progress-engine.ts` (新規)
```typescript
import { DurableObject } from 'cloudflare:workers';

// インターフェース型定義
export interface ProcessingState {
  fileId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number; // 0-100
  stage: string;
  result?: {
    markdown?: string;
    html?: string;
  };
  error?: string;
  updatedAt?: string; // ISO timestamp
}

export class ProgressEngine extends DurableObject<{ ENV: Env }> {
  private state: ProcessingState | null = null;
  private readonly webSockets: Set<WebSocket> = new Set();

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.ctx.blockConcurrencyWhile(async () => {
      // 初期状態をKVから復元（オプション）
      const stored = await this.ctx.storage.get<ProcessingState>('state');
      if (stored) this.state = stored;
    });
  }

  /**
   * WebSocket接続ハンドラー
   */
  async fetch(request: Request): Promise<Response> {
    if (request.headers.get('upgrade') !== 'websocket') {
      return new Response('Expected WebSocket', { status: 426 });
    }

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);

    // クライアントを受け入れ
    server.accept();
    this.webSockets.add(server);

    // 初期状態送信
    if (this.state) {
      server.send(JSON.stringify(this.state));
    }

    // クライアントからのメッセージ処理（現状は受信専用だが拡張性のため）
    server.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        // 例: クライアントからキャンセルリクエスト等
        // if (data.type === 'cancel') { this.cancelProcessing(); }
      } catch (e) {
        console.warn('Invalid WebSocket message:', e);
      }
    });

    // クライアント切断時のクリーンアップ
    server.addEventListener('close', () => {
      this.webSockets.delete(server);
    });

    return new Response(null, { status: 101, webSocket: client });
  }

  /**
   * 進捗状態を更新し、全WebSocketクライアントにブロードキャスト
   */
  async updateProgress(state: ProcessingState) {
    this.state = state;
    this.state.updatedAt = new Date().toISOString();

    // KVにもバックアップ（フォールバック用）
    try {
      await this.ctx.storage.put('state', this.state);
    } catch (e) {
      console.warn('Failed to backup progress to storage:', e);
    }

    // 全WebSocketクライアントに送信
    const message = JSON.stringify(this.state);
    for (const ws of this.webSockets) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(message);
      }
    }
  }

  /**
   * WebSocket経由でクエリに応答（HTTPフォールバック用）
   */
  async queryProgress(): Promise<ProcessingState | null> {
    return this.state;
  }

  /**
   * 進捗状態をクリア（完了後のクリーンアップ用）
   */
  async clear() {
    this.state = null;
    await this.ctx.storage.delete('state');
    
    // 全クライアントにクリア通知
    const message = JSON.stringify(null);
    for (const ws of this.webSockets) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(message);
      }
    }
  }
}

/**
 * WebSocketPair タイプ宣言（Workers環境用）
 */
interface WebSocketPair {
  0: WebSocket;
  1: WebSocket;
}
declare const WebSocketPair: {
  new (): WebSocketPair;
  prototype: WebSocketPair;
};
```

**確認**: `npx tsc --noEmit` で型エラーなし
**注意**: Cloudflare Workers では `WebSocketPair` がグローバル利用可能

---

## ステップ3: 進捗管理ルート作成（WebSocket エンドポイント）
**ファイル**: `src/routes/progress.ts` (新規)
```typescript
import { Hono } from 'hono';
import type { Env } from '../lib/types';
import { ProgressEngine, ProcessingState } from '../lib/progress-engine';
import { validate } from '../lib/validation';
import { getValidatedParams } from '../lib/validation';
import { fileIdParam } from '../lib/schemas';
import { ValidationError } from '../lib/errors';

export function registerProgressRoutes(app: Hono<{ Bindings: Env }>) {
  /**
   * GET /api/progress/:fileId - WebSocket接続エンドポイント
   * クライアントはここでWebSocket接続を確立し、進捗をリアルタイム受信
   */
  app.get('/api/progress/:fileId', async (c) => {
    try {
      // Durable Object の stub 取得
      const id = c.env.PROGRESS_DO.idFromString(c.req.param('fileId'));
      const stub = c.env.PROGRESS_DO.get(id);
      
      // WebSocket アップグレードリクエストを DO に転送
      return stub.fetch(c.req.raw);
    } catch (err) {
      console.error('Progress WebSocket error:', err);
      return c.json({ error: 'Failed to establish progress connection' }, 500);
    }
  });

  /**
   * HTTP フォールバック: KVポーリング互換エンドポイント
   * WebSocket非対応環境や簡易ポーリング用
   */
  app.get('/api/progress/:fileId/http',
    validate({ params: fileIdParam }),
    async (c) => {
      try {
        const fileId = getValidatedParams<{ fileId: string }>(c).fileId;
        const id = c.env.PROGRESS_DO.idFromString(fileId);
        const stub = c.env.PROGRESS_DO.get(id);
        
        // DOのクエリメソッド呼び出し
        const state = await stub.queryProgress();
        if (!state) {
          return c.json({ error: 'Progress not found' }, 404);
        }
        
        return c.json(state);
      } catch (err) {
        console.error('Progress HTTP query error:', err);
        return c.json({ error: 'Failed to query progress' }, 500);
      }
    }
  );
}

/**
 * index.ts でルート登録
 * import { registerProgressRoutes } from './routes/progress';
 * registerProgressRoutes(app);
 */
```

---

## ステップ4: 既存プロセスルート修正（DO連携）
**対象ファイル**: `src/routes/process.ts`
- 現在: KV に直接書き込み
- 改善: Durable Object に進捗更新を委譲

```typescript
// process.ts 修正
import { registerProgressRoutes } from './progress'; // 追加

export function registerProcessRoutes(app: Hono<{ Bindings: Env }>) {
  // ... 既存ルート unchanged

  // POST /api/process/:fileId - 初期化
  app.post('/api/process/:fileId', async (c) => {
    try {
      // ... 既存バリデーション・ファイル存在チェック unchanged

      const body = await c.req.json().catch(() => ({}));
      
      // 初期状態作成
      const initialState: ProcessingState = {
        fileId,
        status: 'processing',
        progress: 0,
        stage: '処理を開始しました',
        error: undefined
      };

      // Durable Object に状態を設定
      const id = c.env.PROGRESS_DO.idFromString(fileId);
      const stub = c.env.PROGRESS_DO.get(id);
      await stub.fetch(
        new Request(`http://localhost/update`, {
          method: 'POST',
          body: JSON.stringify({ type: 'update', state: initialState }),
          headers: { 'Content-Type': 'application/json' }
        })
      );

      // 後方互換性のためKVにも保存（フォールバック用）
      await c.env.PROCESSING_KV.put(`process:${fileId}`, JSON.stringify({
        ...initialState,
        options: body.options || {},
        startedAt: new Date().toISOString()
      }));

      return c.json(initialState);
    } catch (error) {
      console.error('Process init error:', error);
      return c.json({ error: 'Failed to initialize processing' }, 500);
    }
  });

  // PUT /api/process/:fileId/progress - 進捗更新
  app.put('/api/process/:fileId/progress', async (c) => {
    try {
      const fileId = c.req.param('fileId');
      if (!/^[a-f0-9]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(fileId)) {
        return c.json({ error: 'Invalid fileId format' }, 400);
      }

      const existing = await c.env.PROCESSING_KV.get(`process:${fileId}`);
      if (!existing) {
        return c.json({ error: 'Process not found' }, 404);
      }

      const body = await c.req.json();
      const progress = Math.max(0, Math.min(100, Number(body.progress) || 0));
      const stage = typeof body.stage === 'string' ? body.stage.slice(0, 200) : '';
      const status = ['pending', 'processing', 'completed', 'failed'].includes(body.status)
        ? body.status
        : 'processing';

      const state: ProcessingState = {
        fileId,
        status,
        progress,
        stage,
        result: body.result,
        error: body.error
      };

      // Durable Object に更新（メイン経路）
      const id = c.env.PROGRESS_DO.idFromString(fileId);
      const stub = c.env.PROGRESS_DO.get(id);
      await stub.fetch(
        new Request(`http://localhost/update`, {
          method: 'POST',
          body: JSON.stringify({ type: 'update', state }),
          headers: { 'Content-Type': 'application/json' }
        })
      );

      // 後方互換性のためKVにも更新（フォールバック用）
      await c.env.PROCESSING_KV.put(`process:${fileId}`, JSON.stringify({
        ...JSON.parse(existing),
        ...state,
        updatedAt: new Date().toISOString()
      }));

      return c.json(state);
    } catch (error) {
      console.error('Progress update error:', error);
      return c.json({ error: 'Failed to update progress' }, 500);
    }
  });

  // GET /api/process/:fileId - 現在状態取得
  app.get('/api/process/:fileId', async (c) => {
    try {
      const fileId = c.req.param('fileId');
      if (!/^[a-f0-9]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(fileId)) {
        return c.json({ error: 'Invalid fileId format' }, 400);
      }

      // まずDurable Objectから取得を試す
      const id = c.env.PROGRESS_DO.idFromString(fileId);
      const stub = c.env.PROGRESS_DO.get(id);
      const state = await stub.fetch(
        new Request(`http://localhost/query`, { method: 'GET' })
      );

      if (state.ok) {
        const jsonState = await state.json();
        if (jsonState !== null) {
          return c.json(jsonState);
        }
      }

      // フォールバック: KVから取得
      const stateJson = await c.env.PROCESSING_KV.get(`process:${fileId}`, 'json');
      if (!stateJson) {
        return c.json({ error: 'Process not found' }, 404);
      }

      return c.json(stateJson);
    } catch (error) {
      console.error('Get process error:', error);
      return c.json({ error: 'Failed to get processing state' }, 500);
    }
  });

  // ... 他のルート unchanged

  // 進捗ルート登録
  registerProgressRoutes(app);
}
```

**注意点**: 
- DO の `fetch` メソッドでカスタムパス(`/update`, `/query`)を使用して操作を区別
- 後方互換性のため KV への書き込みは残す（DO 障害時のフォールバック）
- 初回は DO 優先、失敗時は KV フォールバック

---

## ステップ5: クライアントサイド WebSocket 接続実装ガイド
**ファイル**: `docs/client/progress-websocket.md` (新規)
```markdown
# クライアントサイド進捗WebSocket接続ガイド

## 接続手順
1. ファイルアップロード後に取得した `fileId` を使用
2. `wss://<your-worker>.workers.dev/api/progress/${fileId}` にWebSocket接続
3. 接続後、サーバーから以下の形式のJSONメッセージを受信:
   ```json
   {
     "fileId": "...",
     "status": "processing",
     "progress": 45,
     "stage": "OCR解析中",
     "updatedAt": "2026-09-16T12:34:56.789Z"
   }
   ```
4. `status` が `completed` または `failed` になったら接続を閉じる
5. 接続切断時は自動的に再接続（指数バックオフ推奨）

## サンプルコード (JavaScript)
```javascript
class ProgressClient {
  constructor(fileId, onUpdate, onError) {
    this.fileId = fileId;
    this.onUpdate = onUpdate;
    this.onError = onError;
    this.ws = null;
    this.retryCount = 0;
    this.maxRetries = 5;
  }

  connect() {
    const ws = new WebSocket(
      `wss://${window.location.host}/api/progress/${this.fileId}`
    );

    ws.onopen = () => {
      console.log('Progress WebSocket connected');
      this.retryCount = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data === null) {
            // サイドからのクリア信号
            this.onUpdate(null);
            this.close();
            return;
        }
        this.onUpdate(data);
        
        if (data.status === 'completed' || data.status === 'failed') {
            this.close();
        }
      } catch (e) {
          this.onError(e);
      }
    };

    ws.onerror = (error) => {
        this.onError(error);
    };

    ws.onclose = () => {
        console.log('Progress WebSocket closed');
        this.ws = null;
        // 再接続ロジック（指数バックオフ）
        if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            setTimeout(() => this.connect(), Math.min(1000 * 2 ** this.retryCount, 30000));
        }
    };

    this.ws = ws;
  }

  close() {
    if (this.ws) {
        this.ws.close();
        this.ws = null;
    }
  }
}
```

## HTTPフォールバック（ポーリング）
WebSocketが利用できない環境では:
```javascript
async function pollProgress(fileId, onUpdate, onError) {
    while (true) {
        try {
            const response = await fetch(`/api/progress/${fileId}/http`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            onUpdate(data);
            if (data.status === 'completed' || data.status === 'failed') break;
            await new Promise(r => setTimeout(r, 2000)); // 2秒間隔
        } catch (error) {
            onError(error);
            await new Promise(r => setTimeout(r, 5000)); // エラー時は5秒待機
        }
    }
}
```
```

---

## ステップ6: 後方互換性テスト・移行戦略
**ファイル**: `src/routes/__tests__/progress-do-migration.test.ts` (新規)
- 既存KVベースの進捗更新がDO経由でも正常動作するか
- DO障害時のKVフォールバック動作確認
- 両方同時書き込みによる整合性テスト
- クライアント側WebSocket接続・メッセージ受信テスト（モック使用）

---

## ステップ7: モニタリング・メトリクス追加
**ファイル**: `src/lib/progress-metrics.ts` (新規)
- アクティブWebSocket接続数
- 進捗更新頻度（リクエスト/秒）
- ブロードキャストメッセージサイズ
- DOインスタンス作成/破棄率

```typescript
// ProgressEngine に追加
private readonly metrics = {
    activeConnections: 0,
    totalUpdates: 0,
    broadcastBytes: 0
};

async updateProgress(state: ProcessingState) {
    // ... 既存処理
    
    this.metrics.totalUpdates++;
    const message = JSON.stringify(this.state);
    this.metrics.broadcastBytes += message.length * 2; // UTF-16近似
    
    // ... ブロードキャスト処理
}

// メトリクス取得メソッド
getMetrics() {
    return { ...this.metrics, activeConnections: this.webSockets.size };
}
```

**エンドポイント追加**: `/api/metrics/progress` で DO メトリクス集約公開

---

## ステップ8: 設定・チューニングガイド
**ファイル**: `docs/operational/progress-do.md` (新規)
- DOインスタンス数の見積もり式: `アクティブファイル数 × 1.2`（バッファ）
- メモリ使用量見積もり: 1インスタンスあたり数KB～十数KB
- スケーリング挙度: 自動（リクエストに応じてインスタンス生成）
- 故障対応: DOクラッシュ時は自動再起動、状態はストレージ（KV）より復元

---

## ステップ9: パフォーマンス比較ベンチマーク
**ファイル**: `benchmark/progress-do-vs-kv.ts` (新規)
- シナリオ: 100ファイル同時処理、各ファイルで10回進捗更新
- KVポーリング方式: クライアントが2秒間隔で10回 polling → 100ファイル × 10回 = 1,000 KV読み込み
- DO方式: 
  - 初期接続: 100 WebSocket接続（DO作成）
  - 進捗更新: 100ファイル × 10回 = 1,000 DO更新（内部処理のみ、外部I/Oなし）
  - ブロードキャスト: 1,000メッセージ × 100クライアント = 100,000 メッセージ送信（ただしメモリ内）
- 結果期待値: KV読み込み書き込み 90%+ 削減、レイテンシ大幅改善

**完了条件**:
- [ ] WebSocketエンドポイント `/api/progress/:fileId` が実装済み
- [ ] HTTPフォールバックエンドポイント `/api/progress/:fileId/http` が実装済み
- [ ] 既存プロセスルートがDO経由で進捗更新（KVフォールバック付き）
- [ ] クライアントサイド実装ガイドがドキュメント化済み
- [ ] テストでDO連携・フォールバック・エラーケース網羅
- [ ] ベンチマークでKVアクセス削減効果確認
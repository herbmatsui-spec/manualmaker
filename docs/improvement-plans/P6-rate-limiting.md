# P6: スライディングウィンドウ レート制限

## 概要
KVを使用したスライディングウィンドウアルゴリズムにより、IP単位およびファイルID単位のレート制限を実装し、サービス悪用や誤ったリクエストからシステムを保護する。

---

## ステップ1: レート制限アルゴリズム実装
**ファイル**: `src/lib/rate-limiter.ts` (新規)
```typescript
import type { Env } from '../lib/types';
import { RateLimitError } from '../lib/errors';

interface RateLimitConfig {
  windowMs: number; // タイムウィンドウサイズ（ミリ秒）
  maxRequests: number; // ウィンドウ内最大リクエスト数
  keyPrefix: string; // KVキーのプレフィックス
}

export class SlidingWindowRateLimiter {
  constructor(
    private readonly kv: KVNamespace,
    private readonly config: RateLimitConfig
  ) {}

  /**
   * リクエストが制限内かチェックし、現在のカウントをインクリメント
   * @param key 識別キー（IPアドレスやfileIdなど）
   * @returns 許可される場合true、制限超過の場合falseと推奨待機秒数
   */
  async consume(key: string): Promise<{ allowed: true } | { allowed: false; retryAfter: number }> {
    const now = Date.now();
    const windowStart = now - this.config.windowMs;
    
    // KVのsorted set（実際はリストとTTLを使用した簡易実装）を使ったスライディングウィンドウ
    // より正確にはRedisのようなsorted setが必要だが、KVの制約により簡易版を実装
    
    const kvKey = `${this.config.keyPrefix}:${key}`;
    
    // 現在のタイムスタンプを追加
    await this.kv.put(
      `${kvKey}:${now}`, 
      '1', 
      { expirationTtl: Math.ceil(this.config.windowMs / 1000) + 1 }
    );
    
    // ウィンドウ内のリクエスト数をカウント（リスト取得 + フィルタリング）
    // 注意: これは効率的ではないが、デモ目的。実装では以下のいずれかを検討:
    // 1. フィックスドウィンドウカウンター（簡易だがバースト許容）
    // 2. 漏れバケットアルゴリズム
    // 3. 外部サービス（Upstash Redis等）使用
    
    // 簡易実装: プレフィックス一致キーをリストし、ウィンドウ内のものをカウント
    const list = await this.kv.list({ 
      prefix: `${kvKey}:`, 
      limit: 1000 // 実際にはページングが必要だが、ここでは制限数を超えない前提
    });
    
    const recentRequests = list.keys
      .map(k => parseInt(k.name.split(':').pop() || '0', 10))
      .filter(timestamp => timestamp >= windowStart)
      .length;
    
    if (recentRequests > this.config.maxRequests) {
      // 最も古いリクエストのタイムスタンプから待機時間計算
      const oldestTimestamp = Math.min(
        ...list.keys
          .map(k => parseInt(k.name.split(':').pop() || '0', 10))
          .filter(timestamp => timestamp >= windowStart)
      );
      
      const retryAfter = Math.ceil((oldestTimestamp + this.config.windowMs - now) / 1000);
      return { allowed: false, retryAfter: Math.max(1, retryAfter) };
    }
    
    return { allowed: true };
  }
}

/**
 * ファクトリ関数
 */
export function createRateLimiter(env: Env, config: RateLimitConfig) {
  return new SlidingWindowRateLimiter(env.PROCESSING_KV, config);
}

/**
 * 事前定義されたレートリミッター設定
 */
export const rateLimitConfigs = {
  upload: {
    windowMs: 60 * 1000, // 1分
    maxRequests: 10, // 1分間に10回
    keyPrefix: 'ratelimit:upload'
  },
  geminiProxy: {
    windowMs: 60 * 1000, // 1分
    maxRequests: 30, // 1分間に30回（Gemini APIの無料枠考慮）
    keyPrefix: 'ratelimit:gemini'
  },
  visionProxy: {
    windowMs: 60 * 1000, // 1分
    maxRequests: 20, // 1分間に20回（Vision APIの無料枠考慮）
    keyPrefix: 'ratelimit:vision'
  },
  progressUpdate: {
    windowMs: 10 * 1000, // 10秒
    maxRequests: 6, // 10秒間に6回（1秒に1回程度に制限）
    keyPrefix: 'ratelimit:progress'
  },
  ipGeneral: {
    windowMs: 60 * 1000, // 1分
    maxRequests: 100, // 1分間に100回（一般的なAPI保護）
    keyPrefix: 'ratelimit:ip'
  }
};
```

**注意**: これは概念実装。実際の本番環境では、より効率的なアルゴリズムや外部サービスを検討する。

---

## ステップ2: レート制限ミドルウェア作成
**ファイル**: `src/lib/rate-limit-middleware.ts` (新規)
```typescript
import { Context, Next } from 'hono';
import { RateLimitError } from '../lib/errors';
import { createRateLimiter, rateLimitConfigs } from './rate-limiter';

export function rateLimit(configKey: keyof typeof rateLimitConfigs, opts: { 
  keyExtractor?: (c: Context) => string; 
  skipFailed?: boolean; 
} = {}) {
  const { keyExtractor, skipFailed = true } = opts;
  
  return async (c: Context, next: Next) => {
    // 環境変数でレート制限無効化（開発時便利）
    if (c.env.RATE_LIMIT_ENABLED === 'false') {
      return await next();
    }
    
    try {
      const config = rateLimitConfigs[configKey];
      const limiter = createRateLimiter(c.env, config);
      
      // キー抽出関数
      const getKey = keyExtractor || ((c: Context) => {
        // デフォルト: IPアドレス（CFが挿入するヘダー使用）
        return c.req.header('cf-connecting-ip') || 'unknown';
      });
      
      const key = getKey(c);
      const result = await limiter.consume(key);
      
      if (!result.allowed) {
        throw new RateLimitError(result.retryAfter);
      }
      
      await next();
    } catch (err) {
      if (err instanceof RateLimitError) {
        return c.json(
          { error: 'Too many requests', retryAfter: err.details?.retryAfter },
          429
        );
      }
      
      if (!skipFailed) {
        throw err; // 失敗時もカウントさせたい場合
      }
      
      // 失敗時はレート制限適用しない（オプション）
      await next();
    }
  };
}

// 特定用途のミドルウェアヘルパー
export const rateLimitUpload = rateLimit('upload', {
  keyExtractor: (c) => c.req.header('cf-connecting-ip') || 'unknown'
});

export const rateLimitGeminiProxy = rateLimit('geminiProxy', {
  keyExtractor: (c) => c.req.header('cf-connecting-ip') || 'unknown'
});

export const rateLimitVisionProxy = rateLimit('visionProxy', {
  keyExtractor: (c) => c.req.header('cf-connecting-ip') || 'unknown'
});

export const rateLimitProgressUpdate = rateLimit('progressUpdate', {
  keyExtractor: (c) => {
    // fileId単位で制限（悪意あるポーリング防止）
    const fileId = c.req.param('fileId');
    return fileId || (c.req.header('cf-connecting-ip') || 'unknown');
  }
});

export const rateLimitIPGeneral = rateLimit('ipGeneral', {
  keyExtractor: (c) => c.req.header('cf-connecting-ip') || 'unknown'
});
```

---

## ステップ3: 各ルートへの適用
**対象ファイル**: 全 `src/routes/*.ts`

**アップロードルート (upload.ts)**:
```typescript
import { rateLimitUpload } from '../lib/rate-limit-middleware';

export function registerUploadRoutes(app: Hono<{ Bindings: Env }>) {
  app.post('/api/upload',
    rateLimitUpload(), // IP単位レート制限
    // ... 他のミドルウェア
    async (c) => { ... }
  );
  
  // 一覧取得も制限（ただし緩めに）
  app.get('/api/uploads',
    rateLimit('ipGeneral'), 
    // ... 
    async (c) => { ... }
  );
}
```

**Gemini/Visionプロキシルート**:
```typescript
// gemini.ts
import { rateLimitGeminiProxy } from '../lib/rate-limit-middleware';

app.post('/api/gemini/:model/:method',
  rateLimitGeminiProxy(),
  // ...
  async (c) => { ... }
);

// vision.ts
import { rateLimitVisionProxy } from '../lib/rate-limit-middleware';

app.post('/api/vision/annotate',
  rateLimitVisionProxy(),
  // ...
  async (c) => { ... }
);
```

**進捗更新ルート (process.ts)**:
```typescript
import { rateLimitProgressUpdate } from '../lib/rate-limit-middleware';

app.put('/api/process/:fileId/progress',
  rateLimitProgressUpdate(), // fileId単位制限
  // ...
  async (c) => { ... }
);
```

**一般的な保護**: 全エンドポイントに基本レート制限を適用するオプション
```typescript
// index.ts でグローバル適用（オプション）
app.use('*', rateLimitIPGeneral()); // 1分間に100リクエストで一般保護
```

---

## ステップ4: KVキーのページング対応改良
**課題**: ステップ1の実装では `list({ limit: 1000 })` が制限を超える可能性あり
**改良案**: 実際の本番実装では以下のいずれかを検討

**オプション1: フィックスドウィンドウカウンター（簡易版）**
```typescript
// rate-limiter.ts 簡易版
async consume(key: string): Promise<{ allowed: true } | { allowed: false; retryAfter: number }> {
  const kvKey = `ratelimit:${this.config.keyPrefix}:${key}`;
  const windowKey = `${kvKey}:${Math.floor(Date.now() / (this.config.windowMs / 1000))}`;
  
  // 現在のウィンドウのカウントをインクリメント
  const current = await this.kv.get(windowKey);
  const count = current ? parseInt(current, 10) + 1 : 1;
  
  // 有効期限設定（ウィンドウサイズ+少し余裕）
  await this.kv.put(windowKey, String(count), { 
    expirationTtl: Math.ceil(this.config.windowMs / 1000) + 10 
  });
  
  if (count > this.config.maxRequests) {
    const resetTime = (Math.floor(Date.now() / (this.config.windowMs / 1000)) + 1) * (this.config.windowMs / 1000) * 1000;
    const retryAfter = Math.ceil((resetTime - Date.now()) / 1000);
    return { allowed: false, retryAfter: Math.max(1, retryAfter) };
  }
  
  return { allowed: true };
}
```
**トレードオフ**: ウィンドウ境界でバーストが発生しやすいが実装が簡単

**オプション2: 漏れバケットアルゴリズム**
- 実装やや複雑だが、より滑らかな制限特性

**採用方針**: まずはオプション1（フィックスドウィンドウ）で実装し、必要に応じて改良

---

## ステップ5: カスタムヘダー・レスポンス強化
**ファイル**: `src/lib/rate-limit-middleware.ts` 修正
- `Retry-After` ヘダーの追加
- `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` ヘダー（オプション）
- 成功時にもヘダー追加でクライアント側での制御可能に

```typescript
// rateLimitミドルウェア内部で
if (!result.allowed) {
  const headers = new Headers();
  headers.set('Retry-After', String(result.retryAfter));
  // 以下はオプションだが有用
  // headers.set('RateLimit-Limit', String(config.maxRequests));
  // headers.set('RateLimit-Remaining', '0');
  // headers.set('RateLimit-Reset', String(Date.now() + result.retryAfter * 1000));
  
  return c.json(
    { error: 'Too many requests' },
    429,
    { headers }
  );
}

// 成功時にもヘダー追加（オプション）
const headers = new Headers();
// headers.set('RateLimit-Limit', String(config.maxRequests));
// headers.set('RateLimit-Remaining', String(Math.max(0, config.maxRequests - currentCount)));
// headers.set('RateLimit-Reset', String(resetTime));
if (headers.size > 0) {
  c.res.headers.set(headers);
}
```

---

## ステップ6: 除外リスト・ホワイトリスト機能
**ファイル**: `src/lib/rate-limiter.ts` 拡張
- 特定IPやファイルIDのレート制限除去（信頼できるサービス内部からの呼び出し等）
- 開発環境での自動除外

```typescript
// rate-limiter コンストラクタ拡張
constructor(
  private readonly kv: KVNamespace,
  private readonly config: RateLimitConfig,
  private readonly whitelist: Set<string> = new Set()
) {}

async consume(key: string): Promise<{ allowed: true } | { allowed: false; retryAfter: number }> {
  // ホワイトリストチェック
  if (this.whitelist.has(key)) {
    return { allowed: true };
  }
  
  // ... 既存制限ロジック
}
```

**使用例**:
```typescript
// index.ts で
const trustedIps = new Set(['127.0.0.1', '::1', '10.0.0.5']); // 内部サービスIP
app.use('*', rateLimitIPGeneral({
  keyExtractor: (c) => c.req.header('cf-connecting-ip') || 'unknown',
  skipFailed: false
}), {
  // ここでwhitelistを渡すにはファクトリ関数が必要だが、簡易版として環境変数から読む
});
// または、環境変数 RATE_LIMIT_WHITELIST="127.0.0.1,::1" 等から読む
```

---

## ステップ7: レート制限状態モニタリングエンドポイント
**ファイル**: `src/routes/metrics.ts` (新規 または既存metricsに追加)
```typescript
import { Hono } from 'hono';
import type { Env } from '../lib/types';

export function registerMetricsRoutes(app: Hono<{ Bindings: Env }>) {
  app.get('/api/metrics/rate-limit', async (c) => {
    try {
      // レート制限関連の KV キーをサンプリングして統計出力
      // 実際には別途メトリクス収集仕組みが必要だが、簡易版
      
      const now = Date.now();
      const oneHourAgo = now - 60 * 60 * 1000;
      
      // この実装はデモ目的。実際の本番では以下が必要:
      // 1. レート制限ミドルウェア内でメトリクス収集（カウンターインクリメント）
      // 2. KVまたは外部サービスにメトリクス保存
      // 3. ここで集約表示
      
      return c.json({
        timestamp: new Date().toISOString(),
        note: 'Rate limit metrics require separate collection mechanism',
        suggestions: [
          'Use external monitoring service (Prometheus + Grafana)',
          'Implement internal counter middleware',
          'Log rate limit events to external service'
        ]
      });
    } catch (error) {
      console.error('Rate limit metrics error:', error);
      return c.json({ error: 'Failed to get rate limit metrics' }, 500);
    }
  );
}
```

---

## ステップ8: テスト・シナリオ作成
**ファイル**: `src/lib/__tests__/rate-limit.test.ts` (新規)
- 正常系: 制限内リクエストは通過
- 境界値: 制限ちょうどで通過、1回超えで制限
- 時間経過: ウィンドウ przesz過後はリセット
- 複数キー: 異なるIP/fileIdは独立して制限
- ホワイトリスト: 指定キーは制限無視
- ヘダー返却: `Retry-After` 等が正常

**テストケース例**:
```typescript
describe('SlidingWindowRateLimiter', () => {
  let kvMock: KVNamespace;
  let limiter: SlidingWindowRateLimiter;
  
  beforeEach(() => {
    // KVのモック実装（簡易版）
    const store = new Map<string, { value: string; expiration: number }>();
    kvMock = {
      get: async (key: string) => {
        const item = store.get(key);
        if (!item || Date.now() > item.expiration) {
          store.delete(key);
          return null;
        }
        return item.value;
      },
      put: async (key: string, value: string, opts: { expirationTtl?: number } = {}) => {
        const expiration = Date.now() + (opts.expirationTtl ?? 60) * 1000;
        store.set(key, { value, expiration });
        return Promise.resolve();
      },
      list: async (options: { prefix?: string; limit?: number } = {}) => {
        const prefix = options.prefix ?? '';
        const limit = options.limit ?? 1000;
        const matchingKeys = Array.from(store.keys())
          .filter(key => key.startsWith(prefix))
          .slice(0, limit);
        
        return {
          keys: matchingKeys.map(key => ({ name: key }))
        };
      },
      delete: async (key: string) => {
        store.delete(key);
        return Promise.resolve();
      }
    } as unknown as KVNamespace;
    
    limiter = new SlidingWindowRateLimiter(kvMock, {
      windowMs: 60000, // 1分
      maxRequests: 5,
      keyPrefix: 'test'
    });
  });
  
  it('should allow requests under limit', async () => {
    for (let i = 0; i < 5; i++) {
      const result = await limiter.consume('test-key');
      expect(result.allowed).toBe(true);
    }
  });
  
  it('should reject requests over limit', async () => {
    // 5回まで許可
    for (let i = 0; i < 5; i++) {
      const result = await limiter.consume('test-key');
      expect(result.allowed).toBe(true);
    }
    
    // 6回目で制限
    const result = await limiter.consume('test-key');
    expect(result.allowed).toBe(false);
    expect(result.retryAfter).toBeGreaterThan(0);
  });
  
  // ... 他のテストケース
});
```

---

## ステップ9: ドキュメント化・運用ガイド
**ファイル**: `docs/operational/rate-limiting.md` (新規)
- レート限定の設計選択理由
- 各エンドポイント別推奨設定値
- 監視とアラート設定ガイド
- 誤ってブロックされた場合の手動解除手順（KVキー削除）
- パフォーマンス影響評価
- 将来の改善方向（外部サービス連携等）

**推奨設定値例**:
| エンドポイント | ウィンドウ | 最大リクエスト | 説明 |
|----------------|------------|----------------|------|
| アップロード | 1分 | 10回 | 大容量ファイルのため控えめ |
| Geminiプロキシ | 1分 | 30回 | API無料枠考慮 |
| Visionプロキシ | 1分 | 20回 | 同上 |
| 進捗更新 | 10秒 | 6回 | ポーリング抑制のため厳め |
| 一般IP保護 | 1分 | 100回 | 基本的なDoS保護 |
| ヘルスチェック | 10秒 | 20回 | 頻繁な監視を許可 |

---

## 完了条件
- [ ] レート制限ミドルウェアが実装済み
- [ ] アップロード、Gemini/Visionプロキシ、進捗更新に適切な制限適用
- [ ] 一般的なIPベース保護がオプションで適用可能
- [ ] `429 Too Many Requests` と `Retry-After` ヘダーが正常返却
- [ ] テストで制限動作・ホワイトリスト・エラーケース網羅
- [ ] ドキュメントに設定方法と運用ガイド記載
- [ ] 開発時に環境変数で無効化可能 (`RATE_LIMIT_ENABLED=false`)
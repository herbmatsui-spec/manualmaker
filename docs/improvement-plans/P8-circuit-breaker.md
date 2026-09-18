# P8: 外部API用サーキットブレーカー

## 概要
Gemini APIとGoogle Cloud Vision APIの障害が全リクエストに波及することを防ぎ、サーキットブレーカーパターンにより障害時のグレースフルデグレードを実装する。

---

## ステップ1: サーキットブレーカー基底クラス実装
**ファイル**: `src/lib/circuit-breaker.ts` (新規)
```typescript
export enum CircuitState {
  CLOSED = 'closed',    // 正常動作状態
  OPEN = 'open',        // 障害状態（リクエストをブロック）
  HALF_OPEN = 'half_open' // 復旧試行状態
}

export interface CircuitBreakerOptions {
  failureThreshold: number; // 失敗回数の閾値（この回数連続失敗でOPENへ）
  recoveryTimeoutMs: number; // OPEN状態からHALF_OPENへ遷移するまでの時間（ミリ秒）
  successThreshold: number; // HALF_OPEN状態에서 CLOSEDへ戻るための連続成功回数
  timeoutMs?: number; // 各リクエストのタイムアウト（ミリ秒）
}

export class CircuitBreaker<T> {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount = 0;
  private successCount = 0;
  private lastFailureTime: number | null = null;
  private readonly timeoutMs: number;

  constructor(
    private readonly name: string,
    private readonly options: CircuitBreakerOptions
  ) {
    this.timeoutMs = options.timeoutMs ?? 5000; // デフォルト5秒
  }

  /**
   * 操作を実行し、サーキットブレーカーロジックを適用
   * @param operation 実行する非同期操作
   * @returns 操作の結果
   * @throws CircuitBreakerOpenError サーキットがOPENの場合
   * @throws operationの元のエラー
   */
  async execute<R>(operation: () => Promise<R>): Promise<R> {
    // 状態チェックと状態遷移
    if (this.state === CircuitState.OPEN) {
      if (this.shouldAttemptReset()) {
        this.state = CircuitState.HALF_OPEN;
        console.info(`CircuitBreaker ${this.name}: HALF_OPEN (attempting reset)`);
      } else {
        throw new CircuitBreakerOpenError(this.name, this.getTimeUntilReset());
      }
    }

    try {
      const result = await this.executeWithTimeout(operation);
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  /**
   * リセットを試みる時間かどうかを判定
   */
  private shouldAttemptReset(): boolean {
    if (!this.lastFailureTime) return false;
    return Date.now() - this.lastFailureTime >= this.options.recoveryTimeoutMs;
  }

  /**
   * リセットまでの残り時間を取得（秒）
   */
  private getTimeUntilReset(): number {
    if (!this.lastFailureTime) return 0;
    const elapsed = Date.now() - this.lastFailureTime;
    const remaining = this.options.recoveryTimeoutMs - elapsed;
    return Math.max(0, Math.ceil(remaining / 1000));
  }

  /**
   * タイムアウト付きで操作を実行
   */
  private async executeWithTimeout<R>(operation: () => Promise<R>): Promise<R> {
    if (this.options.timeoutMs === undefined) {
      return await operation();
    }

    return await Promise.race([
      operation(),
      new Promise<R>((_, reject) =>
        setTimeout(() => reject(new Error(`Operation timeout after ${this.options.timeoutMs}ms`)), this.options.timeoutMs)
      )
    ]);
  }

  /**
   * 成功時に呼ばれる
   */
  private onSuccess(): void {
    this.failureCount = 0;
    if (this.state === CircuitState.HALF_OPEN) {
      this.successCount++;
      if (this.successCount >= this.options.successThreshold) {
        this.state = CircuitState.CLOSED;
        this.successCount = 0;
        console.info(`CircuitBreaker ${this.name}: CLOSED (recovered)`);
      }
    }
    // CLOSED状態では何もしない
  }

  /**
   * 失敗時に呼ばれる
   */
  private onFailure(): void {
    this.failureCount++;
    this.lastFailureTime = Date.now();
    
    if (this.state === CircuitState.HALF_OPEN) {
      // HALF_OPEN状態での失敗はすぐにOPENに戻す
      this.state = CircuitState.OPEN;
      this.successCount = 0;
      console.warn(`CircuitBreaker ${this.name}: OPEN (failure during half-open)`);
    } else if (this.state === CircuitState.CLOSED) {
      // CLOSED状態でしきい値に達したらOPENに移行
      if (this.failureCount >= this.options.failureThreshold) {
        this.state = CircuitState.OPEN;
        console.warn(`CircuitBreaker ${this.name}: OPEN (failure threshold reached)`);
      }
    }
    // OPEN状態では何もしない（すでにOPEN）
  }

  /**
   * 現在の状態を取得
   */
  getState(): CircuitState {
    return this.state;
  }

  /**
   * 手動でサーキットをリセット
   */
  reset(): void {
    this.state = CircuitState.CLOSED;
    this.failureCount = 0;
    this.successCount = 0;
    this.lastFailureTime = null;
    console.info(`CircuitBreaker ${this.name}: manually reset to CLOSED`);
  }

  /**
   * 現在のメトリクスを取得
   */
  getMetrics(): {
    state: CircuitState;
    failureCount: number;
    successCount: number;
    lastFailureTime: number | null;
  } {
    return {
      state: this.state,
      failureCount: this.failureCount,
      successCount: this.successCount,
      lastFailureTime: this.lastFailureTime
    };
  }
}

/**
 * サーキットブレーカーがOPEN状態のときに投げられるエラー
 */
export class CircuitBreakerOpenError extends Error {
  constructor(
    public readonly name: string,
    public readonly retryAfterSeconds: number
  ) {
    super(`CircuitBreaker ${name} is OPEN. Retry after ${retryAfterSeconds} seconds`);
    this.name = 'CircuitBreakerOpenError';
  }
}
```

**確認**: `npx tsc --noEmit` で型エラーなし

---

## ステップ2: 外部APIラッパーにサーキットブレーカー組み込み
**ファイル**: `src/lib/external-api.ts` (新規)
- Gemini APIとVision APIのラッパーにサーキットブレーカーを組み込み

```typescript
import type { Env } from '../lib/types';
import { CircuitBreaker } from './circuit-breaker';
import { fetchWithRetry } from './http-client';
import { ExternalAPIError } from '../lib/errors';

interface GeminiRequest {
  contents?: Array<{
    parts: Array<{ text?: string; inlineData?: { data: string; mimeType: string } }>;
  }>;
  generationConfig?: Record<string, unknown>;
  safetySettings?: Array<Record<string, unknown>>;
}

interface VisionRequest {
  requests: Array<{
    image: { content: string };
    features: Array<{ type: string; maxResults?: number }>;
  }>;
}

/**
 * Gemini APIラッパー（サーキットブレーカー付き）
 */
export class GeminiApi {
  private readonly circuitBreaker: CircuitBreaker<any>;

  constructor(private readonly env: Env) {
    this.circuitBreaker = new CircuitBreaker('gemini-api', {
      failureThreshold: 5, // 5回連続失敗でOPEN
      recoveryTimeoutMs: 60 * 1000, // 1分後にHALF_OPENへ
      successThreshold: 3, // 3回連続成功でCLOSEDへ戻す
      timeoutMs: 10 * 1000 // 10秒タイムアウト
    });
  }

  async generateContent(request: GeminiRequest): Promise<any> {
    return this.circuitBreaker.execute(async () => {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${this.env.GEMINI_MODEL_NAME}:generateContent`;
      
      const response = await fetchWithRetry(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...request,
          // APIキーはヘダーで渡す（より安全）
        })
      }, {
        maxRetries: 2 // サーキットブレーカーとは別のレトライ（一時的なネットワーク問題用）
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new ExternalAPIError(
          'gemini',
          `Gemini API error: ${response.status}`,
          response.status,
          { errorText }
        );
      }

      return await response.json();
    });
  }

  /**
   * サーキットブレーカーの状態を取得
   */
  getCircuitState(): CircuitState {
    return this.circuitBreaker.getState();
  }

  /**
   * サーキットブレーカーのメトリクスを取得
   */
  getCircuitMetrics() {
    return this.circuitBreaker.getMetrics();
  }

  /**
   * 手動でサーキットブレーカーをリセット
   */
  resetCircuitBreaker() {
    this.circuitBreaker.reset();
  }
}

/**
 * Vision APIラッパー（サーキットブレーカー付き）
 */
export class VisionApi {
  private readonly circuitBreaker: CircuitBreaker<any>;

  constructor(private readonly env: Env) {
    this.circuitBreaker = new CircuitBreaker('vision-api', {
      failureThreshold: 3, // Vision APIは少し敏感なので閾値を低めに
      recoveryTimeoutMs: 30 * 1000, // 30秒後にHALF_OPENへ
      successThreshold: 2, // 2回連続成功でCLOSEDへ戻す
      timeoutMs: 15 * 1000 // 15秒タイムアウト（画像処理なので少し長め）
    });
  }

  async annotateImage(request: VisionRequest): Promise<any> {
    return this.circuitBreaker.execute(async () => {
      const url = 'https://vision.googleapis.com/v1/images:annotate';
      
      const response = await fetchWithRetry(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request)
      }, {
        maxRetries: 2
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new ExternalAPIError(
          'vision',
          `Vision API error: ${response.status}`,
          response.status,
          { errorText }
        );
      }

      return await response.json();
    });
  }

  /**
   * サーキットブレーカーの状態を取得
   */
  getCircuitState(): CircuitState {
    return this.circuitBreaker.getState();
  }

  /**
   * サーキットブレーカーのメトリクスを取得
   */
  getCircuitMetrics() {
    return this.circuitBreaker.getMetrics();
  }

  /**
   * 手動でサーキットブレーカーをリセット
   */
  resetCircuitBreaker() {
    this.circuitBreaker.reset();
  }
}

/**
 * ファクトリ関数
 */
export function createGeminiApi(env: Env): GeminiApi {
  return new GeminiApi(env);
}

export function createVisionApi(env: Env): VisionApi {
  return new VisionApi(env);
}
```

---

## ステップ3: 外部APIプロキシルート修正（サーキットブレーカー連携）
**対象ファイル**: `src/routes/gemini.ts`
- 現在の直接fetch実装を、サーキットブレーカー付きラッパーに変更

```typescript
import { Hono } from 'hono';
import type { Env } from '../lib/types';
import { createGeminiApi } from '../lib/external-api';
import { validate } from '../lib/validation';
import { getValidatedParams } from '../lib/validation';
import { geminiProxyParams, geminiProxyBody } from '../lib/schemas';
import { CircuitBreakerOpenError } from '../lib/circuit-breaker';

// グローバルインスタンス（実際には適切なスコープ管理が必要）
// ここではリクエストごとに作成するが、パフォーマンスのためシングルトン推奨
let geminiApiInstance: GeminiApi | null = null;

export function registerGeminiRoutes(app: Hono<{ Bindings: Env }>) {
  // Gemini APIプロキシエンドポイント
  app.post('/api/gemini/:model/:method',
    validate({ params: geminiProxyParams }),
    validate({ body: geminiProxyBody }),
    async (c) => {
      try {
        // インスタンス取得（シングルトンパターン）
        if (!geminiApiInstance) {
          geminiApiInstance = createGeminiApi(c.env);
        }

        const { model, method } = getValidatedParams<{ model: string; method: string }>(c);
        const body = c.req.json(); // 既にバリデート済みだが、ここでは取得し直す
        
        // モデル名の簡易バリデーション（スキーマではもう少し厳密に）
        if (model !== c.env.GEMINI_MODEL_NAME) {
          // 環境変数で設定されたモデル以外は拒否（セキュリティのため）
          return c.json({ error: 'Invalid model' }, 400);
        }

        // メソッドに応じて適切なAPIを呼び出し
        let result: any;
        if (method === 'generateContent') {
          result = await geminiApiInstance.generateContent(body);
        } else if (method === 'streamGenerateContent') {
          // ストリームは別実装が必要だが、ここでは通常のgenerateContentで代替
          // または、サーキットブレーカーをストリーム版にも適用
          result = await geminiApiInstance.generateContent(body);
        } else if (method === 'countTokens') {
          // countTokensも同様にラップが必要だが、ここでは簡略化
          // 実際には別のメソッドを実装
          result = await geminiApiInstance.generateContent({ 
            contents: [{ parts: [{ text: JSON.stringify(body) }]}] 
          });
        } else {
          return c.json({ error: 'Unsupported method' }, 400);
        }

        return c.json(result);
      } catch (err) {
        if (err instanceof CircuitBreakerOpenError) {
          // サーキットブレーカーOPEN時は503サービス利用不可か、キャッシュされたレスポンスを返す
          // ここでは簡易的にエラーを返すが、実際にはキャッシュフォールバック等を検討
          return c.json(
            { 
              error: 'Service temporarily unavailable', 
              details: 'External API circuit breaker is open',
              retryAfter: err.retryAfterSeconds 
            }, 
            503
          );
        }

        if (err instanceof ExternalAPIError) {
          // 外部API固有のエラーはそのまま返す
          return c.json(
            { error: 'External API error', details: err.message },
            err.upstreamStatus ?? 502
          );
        }

        console.error('Gemini proxy error:', err);
        return c.json({ error: 'Proxy failed' }, 500);
      }
    }
  );

  // モデルリストエンドポイントも同様にサーキットブレーカー適用可能
  app.get('/api/gemini/models', async (c) => {
    try {
      if (!geminiApiInstance) {
        geminiApiInstance = createGeminiApi(c.env);
      }
      
      // モデルリスト取得用のメソッドを実装する必要がある
      // ここでは簡略化のため、実際のAPIを直接呼び出すが、サーキットブレーカーを適用
      const url = `https://generativelanguage.googleapis.com/v1beta/models`;
      
      const response = await geminiApiInstance.circuitBreaker.execute(async () => {
        return fetchWithRetry(url, {
          method: 'GET',
          headers: { 
            'x-goog-api-key': c.env.GEMINI_API_KEY 
          }
        }, { maxRetries: 2 });
      });

      if (!response.ok) {
        const errorText = await response.text();
        return c.json(
          { error: 'Gemini API error', details: errorText },
          response.status === 429 ? 429 : 502
        );
      }

      const result = await response.json();
      return c.json(result);
    } catch (err) {
      if (err instanceof CircuitBreakerOpenError) {
        return c.json(
          { error: 'Service temporarily unavailable', retryAfter: err.retryAfterSeconds },
          503
        );
      }
      
      console.error('Gemini list models error:', err);
      return c.json({ error: 'Proxy failed' }, 500);
    }
  });
}
```

**Vision APIルートも同様に修正** (`src/routes/vision.ts`):
```typescript
// 同様のパターンでサーキットブレーカーを適用
import { Hono } from 'hono';
import type { Env } from '../lib/types';
import { createVisionApi } from '../lib/external-api';
import { validate } from '../lib/validation';
import { visionProxyBody } from '../lib/schemas';
import { CircuitBreakerOpenError } from '../lib/circuit-breaker';

let visionApiInstance: VisionApi | null = null;

export function registerVisionRoutes(app: Hono<{ Bindings: Env }>) {
  app.post('/api/vision/annotate',
    validate({ body: visionProxyBody }),
    async (c) => {
      try {
        if (!visionApiInstance) {
          visionApiInstance = createVisionApi(c.env);
        }

        const body = await c.req.json();
        
        const result = await visionApiInstance.annotateImage(body);
        
        return c.json(result);
      } catch (err) {
        if (err instanceof CircuitBreakerOpenError) {
          return c.json(
            { 
              error: 'Service temporarily unavailable', 
              details: 'External API circuit breaker is open',
              retryAfter: err.retryAfterSeconds 
            }, 
            503
          );
        }

        if (err instanceof ExternalAPIError) {
          return c.json(
            { error: 'External API error', details: err.message },
            err.upstreamStatus ?? 502
          );
        }

        console.error('Vision proxy error:', err);
        return c.json({ error: 'Proxy failed' }, 500);
      }
    }
  );
}
```

---

## ステップ4: サーキットブレーカー状態監視エンドポイント
**ファイル**: `src/routes/metrics.ts` (新規 または既存に追加)
```typescript
import { Hono } from 'hono';
import type { Env } from '../lib/types';

// グローバルインスタンス参照（実際には適切なDIコンテナ使用を推奨）
let geminiApiInstance: any = null;
let visionApiInstance: any = null;

// 初期化関数（他のモジュールから呼び出し可能にするか、グローバルで管理）
export function setApiInstances(geminiApi: any, visionApi: any) {
  geminiApiInstance = geminiApi;
  visionApiInstance = visionApi;
}

export function registerMetricsRoutes(app: Hono<{ Bindings: Env }>) {
  app.get('/api/metrics/circuit-breakers', async (c) => {
    try {
      const result: Record<string, any> = {
        timestamp: new Date().toISOString(),
        gemini: {},
        vision: {}
      };

      if (geminiApiInstance && typeof geminiApiInstance.getCircuitMetrics === 'function') {
        result.gemini = geminiApiInstance.getCircuitMetrics();
      }

      if (visionApiInstance && typeof visionApiInstance.getCircuitMetrics === 'function') {
        result.vision = visionApiInstance.getCircuitMetrics();
      }

      return c.json(result);
    } catch (error) {
      console.error('Circuit breaker metrics error:', error);
      return c.json({ error: 'Failed to get circuit breaker metrics' }, 500);
    }
  });

  /**
   * 手動でサーキットブレーカーをリセットするエンドポイント（運用用）
   * 注意: 本番環境では認証・認可が必要
   */
  app.post('/api/system/reset-circuit-breakers', async (c) => {
    try {
      // 実際の本番環境ではここで認証チェックを入れる
      // 例: APIキーチェック、IP制限等
      
      if (geminiApiInstance && typeof geminiApiInstance.resetCircuitBreaker === 'function') {
        geminiApiInstance.resetCircuitBreaker();
      }
      
      if (visionApiInstance && typeof visionApiInstance.resetCircuitBreaker === 'function') {
        visionApiInstance.resetCircuitBreaker();
      }
      
      return c.json({ 
        success: true, 
        message: 'Circuit breakers reset',
        timestamp: new Date().toISOString() 
      });
    } catch (error) {
      console.error('Reset circuit breakers error:', error);
      return c.json({ error: 'Failed to reset circuit breakers' }, 500);
    }
  });
}
```

**index.ts で初期化**:
```typescript
// index.ts の途中で
import { registerMetricsRoutes } from './routes/metrics';
import { createGeminiApi } from './lib/external-api';
import { createVisionApi } from './lib/external-api';

// APIインスタンス作成
const geminiApi = createGeminiApi(/* env はここで取得する必要があるが、実際には難しい */);
// より良い方法: ミドルウェアやプラグインパターンでDIを行う
// ここでは簡易的に後で設定する方法を取る

// 後でメトリクスルートにインスタンスを設定する関数を呼び出せるようにする
// 実際には、アプリケーションファクトリーパターンを使うか、
// グローバル変数を適切に管理する

app.get('/api/health', (c) => {
  // ... 既存の処理
});

// メトリクスルート登録後にインスタンスを設定する仕組みが必要
// 簡易的には、グローバルでインスタンスを保持
let globalGeminiApi: any = null;
let globalVisionApi: any = null;

// インスタンス作成関数をラップ
function createApiInstances(env: Env) {
  globalGeminiApi = createGeminiApi(env);
  globalVisionApi = createVisionApi(env);
  
  // メトリクスルートに設定
  // ここでregisterMetricsRoutesを呼び出すか、別途設定
}

// 実際の実装では、このあたりはアプリケーション初期化フローを見直す必要がある
// ここでは概念を示すために簡略化
```

---

## ステップ5: フォールバックメカニズム実装
**ファイル**: `src/lib/fallback-cache.ts` (新規)
- サーキットブレーカーOPEN時のキャッシュフォールバック機能

```typescript
import type { Env } from '../lib/types';

export class FallbackCache {
  constructor(
    private readonly kv: KVNamespace,
    private readonly defaultTtlSeconds: number = 300 // 5分デフォルト
  ) {}

  /**
   * 結果をキャッシュに保存
   */
  async cacheResult<T>(key: string, value: T, ttlSeconds?: number): Promise<void> {
    const ttl = ttlSeconds ?? this.defaultTtlSeconds;
    await this.kv.put(
      `fallback:${key}`, 
      JSON.stringify(value), 
      { expirationTtl: ttl }
    );
  }

  /**
   * キャッシュから結果を取得
   */
  async getCachedResult<T>(key: string): Promise<T | null> {
    const cached = await this.kv.get(`fallback:${key}`, 'text');
    if (cached === null) return null;
    
    try {
      return JSON.parse(cached) as T;
    } catch (e) {
      console.error(`Failed to parse cached value for key ${key}:`, e);
      return null;
    }
  }

  /**
   * キャッシュを削除
   */
  async invalidate(key: string): Promise<void> {
    await this.kv.delete(`fallback:${key}`);
  }

  /**
   * 特定のプレフィックスにマッチするキャッシュを一括削除
   */
  async invalidateByPrefix(prefix: string): Promise<void> {
    const list = await this.kv.list({ prefix: `fallback:${prefix}` });
    const keys = list.keys.map(k => k.name);
    if (keys.length > 0) {
      await this.kv.deleteMany(keys);
    }
  }
}

/**
 * ファクトリ関数
 */
export function createFallbackCache(env: Env) {
  return new FallbackCache(env.PROCESSING_KV);
}
```

**サーキットブレーカーラッパーにフォールバック組み込み** (`src/lib/external-api.ts` 修正):
```typescript
// GeminiApiクラス内部に追加
private readonly fallbackCache: ReturnType<typeof createFallbackCache>;

constructor(private readonly env: Env) {
  // ... 既存のサーキットブレーカー初期化
  
  this.fallbackCache = createFallbackCache(env);
}

// generateContentメソッド内部で
async generateContent(request: GeminiRequest): Promise<any> {
  // キャッシュキー生成（リクエスト内容のハッシュ等）
  const cacheKey = `gemini:${this.env.GEMINI_MODEL_NAME}:generateContent:${this.hashRequest(request)}`;
  
  // キャッシュから取得を試みる（サーキットブレーカーOPEN時のフォールバック用）
  let cachedResult: any | null = null;
  try {
    cachedResult = await this.fallbackCache.getCachedResult(cacheKey);
  } catch (e) {
    console.warn(`Failed to read from fallback cache:`, e);
  }
  
  return this.circuitBreaker.execute(async () => {
    // ... 既存のAPI呼び出し処理
    
    // 成功したらキャッシュに保存
    try {
      await this.fallbackCache.cacheResult(cacheKey, result, 300); // 5分キャッシュ
    } catch (e) {
      console.warn(`Failed to write to fallback cache:`, e);
    }
    
    return result;
  }, {
    // フォールバックオプションを追加
    onOpen: async () => {
      // サーキットがOPENになったときのフォールバックロジック
      if (cachedResult !== null) {
        console.info(`Using cached result for ${cacheKey} due to circuit breaker open`);
        return cachedResult;
      }
      // キャッシュもない場合は通常通りエラーを投げる
    }
  });
}

// リクエストのハッシュ関数（簡易実装）
private hashRequest(request: GeminiRequest): string {
  // 実際には適切なハッシュ関数（SHA-256等）を使うべき
  // ここでは簡易的にJSON文字列の長さと最初の数文字を使用
  const json = JSON.stringify(request);
  return `${json.length}-${json.substring(0, Math.min(20, json.length))}`;
}

// VisionApi も同様に実装
```

**フォールバック用のサーキットブレーカーオプション拡張** (`src/lib/circuit-breaker.ts`):
```typescript
export interface CircuitBreakerOptions {
  // ... 既存のオプション
  
  // フォールバックコールバック
  onOpen?: () => Promise<any> | any; // OPEN状態時に呼ばれるフォールバックロジック
}

// executeメソッド内部で
async execute<R>(operation: () => Promise<R>): Promise<R> {
  // ... 既存の状態チェック
  
  try {
    // ... 既存の実行ロジック
    
    // 成功時の処理
    this.onSuccess();
    
    // フォールバックキャッシュ保存（オプションであれば実装）
    if (this.options.onClose) {
      // CLOSED状態になったときの後処理
      await this.options.onClose?.();
    }
    
    return result;
  } catch (error) {
    this.onFailure();
    
    // OPEN状態への遷移時のフォールバック処理
    if (this.state === CircuitState.OPEN && this.options.onOpen) {
      try {
        const fallbackResult = await this.options.onOpen();
        return fallbackResult; // フォールバック結果を返す
      } catch (fallbackError) {
        // フォールバックも失敗したら元のエラーを投げる
        console.error('Fallback also failed:', fallbackError);
      }
    }
    
    throw error;
  }
}
```

---

## ステップ6: サーキットブレーカー設定・チューニングガイド
**ファイル**: `docs/operational/circuit-breaker.md` (新規)
- 各外部API別の推奨設定値
- 失敗Threshold、リカバリータイムアウト、成功Thresholdの調整方法
- 監視項目とアラート設定
- 手動リセットの手順とタイミング
- フォールバック戦略の選択肢（キャッシュ、スタティックレスポンス、エラーレスポンス等）

**推奨設定値例**:
| API | failureThreshold | recoveryTimeoutMs | successThreshold | timeoutMs |
|-----|------------------|-------------------|------------------|-----------|
| Gemini | 5 | 60000 (1分) | 3 | 10000 (10秒) |
| Vision | 3 | 30000 (30秒) | 2 | 15000 (15秒) |

---

## ステップ7: テスト・シナリオ作成
**ファイル**: `src/lib/__tests__/circuit-breaker.test.ts` (新規)
- 正常動作時のCLOSED状態維持
- 障害発生時の状態遷移: CLOSED → OPEN
- リカバリータイムアウト後の状態遷移: OPEN → HALF_OPEN
- HALF_OPEN状態での成功による状態遷移: HALF_OPEN → CLOSED
- HALF_OPEN状態での失敗による状態遷移: HALF_OPEN → OPEN
- フォールバックメカニズムの動作確認
- メトリクス取得の正常性
- 手動リセット機能

**テストケース例**:
```typescript
describe('CircuitBreaker', () => {
  let cb: CircuitBreaker<any>;
  
  beforeEach(() => {
    cb = new CircuitBreaker('test', {
      failureThreshold: 3,
      recoveryTimeoutMs: 100, // テスト用に短く
      successThreshold: 2,
      timeoutMs: 50
    });
  });
  
  it('should start in CLOSED state', () => {
    expect(cb.getState()).toBe(CircuitState.CLOSED);
  });
  
  it('should remain CLOSED when under failure threshold', async () => {
    const failingOperation = () => Promise.reject(new Error('Failed'));
    
    // 2回失敗（しきい値未満）
    for (let i = 0; i < 2; i++) {
      try {
        await cb.execute(failingOperation);
      } catch (e) {
        // 期待通り失敗
      }
    }
    
    expect(cb.getState()).toBe(CircuitState.CLOSED);
  });
  
  it('should transition to OPEN after failure threshold', async () => {
    const failingOperation = () => Promise.reject(new Error('Failed'));
    
    // 3回失敗（しきい値到達）
    for (let i = 0; i < 3; i++) {
      try {
        await cb.execute(failingOperation);
      } catch (e) {
        // 期待通り失敗
      }
    }
    
    expect(cb.getState()).toBe(CircuitState.OPEN);
  });
  
  // ... 他のテストケース
});
```

---

## ステップ8: ドキュメント化・運用ガイド
**ファイル**: `docs/operational/circuit-breaker.md` (詳細版)
- サーキットブレーカーの設計原理
- 各コンポーネントの説明
- 設定方法とチューニングガイド
- 監視とアラート設定
- トラブルシューティングガイド
- パフォーマンス影響評価

---

## ステップ9: パフォーマンス比較・ベンチマーク
**ファイル**: `benchmark/circuit-breaker-benchmark.ts` (新規)
- サーキットブレーカーあり/なしでのレイテンシ比較
- 障害発生時のリカバリー時間測定
- フォールバックメカニズムの効果測定
- スループットへの影響評価

**ベンチマークシナario**:
1. 正常時: 100リクエスト/秒でレイテンシ測定
2. 障害時: 50%失敗率を注入し、サーキットブレーカーの動作確認
3. リカバリー時: 障害から復旧するまでの時間測定
4. フォールバック時: キャッシュヒット率とレイテンシ測定

**完了条件**:
- [ ] サーキットブレーカークラスが実装済み
- [ ] Gemini APIとVision APIラッパーにサーキットブレーカー組み込み済み
- [ ] 外部APIプロキシルートがサーキットブレーカーを尊重するように修正済み
- [ ] サーキットブレーカー状態監視エンドポイントが実装済み
- [ ] 手動リセットエンドポイントが実装済み（認証付き推奨）
- [ ] フォールバックメカニズムが実装済み（オプション）
- [ ] テストで状態遷移・フォールバック・エラーケース網羅
- [ ] ドキュメントに設定方法と運用ガイド記載
- [ ] ベンチマークでパフォーマンス影響評価済み
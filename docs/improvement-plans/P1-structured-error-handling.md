# P1: 構造化エラーハンドリング（エラーコード・相関ID）

## 概要
汎用的な500エラーを廃止し、型付きエラークラス・相関ID・構造化レスポンスでデバッグ性と運用性を向上する。

---

## ステップ1: エラー基底クラスと派生クラス定義
**ファイル**: `src/lib/errors.ts` (新規)
```typescript
export class AppError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly statusCode: number = 500,
    public readonly details?: unknown
  ) {
    super(message);
    this.name = 'AppError';
  }
}

export class ValidationError extends AppError {
  constructor(message: string, details?: unknown) {
    super('VALIDATION_ERROR', message, 400, details);
    this.name = 'ValidationError';
  }
}

export class StorageError extends AppError {
  constructor(message: string, details?: unknown) {
    super('STORAGE_ERROR', message, 500, details);
    this.name = 'StorageError';
  }
}

export class ExternalAPIError extends AppError {
  constructor(
    public readonly service: 'gemini' | 'vision',
    message: string,
    public readonly upstreamStatus?: number,
    details?: unknown
  ) {
    super('EXTERNAL_API_ERROR', message, upstreamStatus === 429 ? 429 : 502, details);
    this.name = 'ExternalAPIError';
  }
}

export class RateLimitError extends AppError {
  constructor(retryAfter: number) {
    super('RATE_LIMIT_EXCEEDED', 'Too many requests', 429, { retryAfter });
    this.name = 'RateLimitError';
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string) {
    super('NOT_FOUND', `${resource} not found`, 404);
    this.name = 'NotFoundError';
  }
}
```

**確認**: `npx tsc --noEmit` で型エラーなし

---

## ステップ2: 相関IDミドルウェア作成
**ファイル**: `src/lib/middleware.ts` (新規)
```typescript
import { Context, Next } from 'hono';

export function correlationId() {
  return async (c: Context, next: Next) => {
    const requestId = c.req.header('x-request-id') || crypto.randomUUID();
    c.set('requestId', requestId);
    c.header('x-request-id', requestId);
    await next();
  };
}

export function errorHandler() {
  return async (c: Context, next: Next) => {
    try {
      await next();
    } catch (err) {
      const requestId = c.get('requestId') || 'unknown';
      console.error(`[${requestId}] Unhandled error:`, err);

      if (err instanceof AppError) {
        return c.json(
          { error: { code: err.code, message: err.message, requestId, details: err.details } },
          err.statusCode
        );
      }

      return c.json(
        { error: { code: 'INTERNAL_ERROR', message: 'Internal server error', requestId } },
        500
      );
    }
  };
}
```

**確認**: 既存ルートで `app.use('*', correlationId(), errorHandler())` 適用後、エラー時に `x-request-id` ヘッダー付与確認

---

## ステップ3: 外部API呼び出しにリトライロジック追加
**ファイル**: `src/lib/http-client.ts` (新規)
```typescript
interface RetryOptions {
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  retryableStatuses?: number[];
}

export async function fetchWithRetry(
  url: string,
  options: RequestInit,
  retryOptions: RetryOptions = {}
): Promise<Response> {
  const {
    maxRetries = 3,
    baseDelayMs = 500,
    maxDelayMs = 5000,
    retryableStatuses = [429, 500, 502, 503, 504]
  } = retryOptions;

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);
      if (!retryableStatuses.includes(response.status)) {
        return response;
      }
      lastError = new Error(`HTTP ${response.status}`);
    } catch (err) {
      lastError = err as Error;
    }

    if (attempt < maxRetries) {
      const delay = Math.min(baseDelayMs * 2 ** attempt, maxDelayMs);
      await new Promise(r => setTimeout(r, delay + Math.random() * 100));
    }
  }

  throw lastError;
}
```

**対象修正**: `src/routes/gemini.ts`, `src/routes/vision.ts` で `fetch` → `fetchWithRetry` 置換

---

## ステップ4: 既存ルートのエラーハンドリング統一
**ファイル**: 全ルートファイル (`src/routes/*.ts`)
- `try-catch` 内で汎用 `Error` 投げず、専用エラークラス使用
- `console.error` に `requestId` 含める（`c.get('requestId')`）

**例 (upload.ts)**:
```typescript
import { ValidationError, StorageError } from '../lib/errors';

// バリデーション失敗
throw new ValidationError('Invalid filename', { filename });

// R2/KVエラー
throw new StorageError('Failed to upload to R2', { key, cause: err });
```

---

## ステップ5: エラーレスポンス形式テスト作成
**ファイル**: `src/routes/__tests__/error-handling.test.ts` (新規)
- 各エラータイプで正しいステータスコード・コード・相関ID返却確認
- リトライ動作確認（モックサーバーで500返却→成功シナリオ）

---

## ステップ6: OpenAPIエラースキーマ定義
**ファイル**: `src/lib/openapi-errors.ts` (新規)
- `@hono/zod-openapi` 用エラーレスポンススキーマ定義
- 全エンドポイントの `responses` に共通エラー定義参照追加

---

## ステップ7: ログ構造化（JSON形式）
**ファイル**: `src/lib/logger.ts` (新規)
- `pino` 風軽量ロガー実装（Cloudflare Workers対応）
- `requestId`, `timestamp`, `level`, `message`, `context` 含むJSON出力
- 本番環境で `wrangler tail --format json` と連携

---

## ステップ8: 監視・アラート用メトリクス収集
**ファイル**: `src/lib/metrics.ts` (新規)
- エラー発生カウンター（エラーコード別、エンドポイント別）
- KV/R2/外部API 別のレイテンシヒストグラム
- `/api/metrics` エンドポイントで Prometheus 形式出力

---

## ステップ9: ドキュメント化・運用ガイド
**ファイル**: `docs/operational/error-handling.md` (新規)
- エラーコード一覧・対応フロー
- 相関IDを用いたログ追跡手順
- インシデント対応ランブック

---

## 完了条件
- [ ] 全エンドポイントが構造化エラー返却
- [ ] 相関IDがリクエスト/レスポンス/ログ全てに伝播
- [ ] 外部API障害時にリトライ→グレースフルデグレード動作
- [ ] テストカバレッジ 80% 以上
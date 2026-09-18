# P2: Zodスキーマによる入力検証

## 概要
全エンドポイントのリクエスト検証をZodスキーマで統一し、バリデーションロジックをミドルウェア化して保守性とセキュリティを向上。

---

## ステップ1: Zod依存確認・共通スキーマ定義
**ファイル**: `src/lib/schemas.ts` (新規)
```typescript
import { z } from 'zod';

// 共通パラメータ
export const fileIdParam = z.object({
  fileId: z.string().regex(/^[a-f0-9]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i, 'Invalid fileId format'),
});

export const paginationQuery = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20),
  offset: z.coerce.number().int().min(0).default(0),
});

// アップロード
export const uploadBody = z.object({
  file: z.instanceof(File).refine(f => f.type === 'application/pdf', 'Only PDF allowed'),
}).passthrough(); // FormData対応

// 処理開始
export const processStartBody = z.object({
  options: z.object({
    compactLayout: z.boolean().optional(),
    useEmojis: z.boolean().optional(),
    promptLayout: z.string().optional(),
    promptStrictMode: z.boolean().optional(),
    promptHasDiagrams: z.boolean().optional(),
    promptLowQualityMode: z.boolean().optional(),
    baseUrl: z.string().url().optional(),
  }).optional(),
});

// 進捗更新
export const progressUpdateBody = z.object({
  progress: z.number().int().min(0).max(100),
  stage: z.string().max(200).optional(),
  status: z.enum(['pending', 'processing', 'completed', 'failed']).optional(),
  result: z.object({
    markdown: z.string().optional(),
    html: z.string().optional(),
  }).optional(),
  error: z.string().optional(),
});

// 結果保存
export const resultSaveBody = z.object({
  markdown: z.string().min(1).max(10 * 1024 * 1024),
  title: z.string().max(300).optional(),
});

// Geminiプロキシ
export const geminiProxyParams = z.object({
  model: z.string().regex(/^[a-z0-9.\-]+$/i, 'Invalid model name'),
  method: z.enum(['generateContent', 'streamGenerateContent', 'countTokens']),
});
export const geminiProxyBody = z.record(z.unknown());

// Visionプロキシ
export const visionProxyBody = z.object({
  requests: z.array(z.object({
    image: z.object({ content: z.string() }),
    features: z.array(z.object({ type: z.string(), maxResults: z.number().optional() })),
  })).max(16),
});

// Mermaid保存
export const mermaidSaveBody = z.object({
  mermaid: z.string().min(1).max(512 * 1024),
});

// PIIマスク
export const piiMaskBody = z.object({
  text: z.string().max(1024 * 1024),
});

// i18n言語検出
export const i18nDetectBody = z.object({
  text: z.string(),
});

// 設定取得（クエリパラメータなし）
export const configQuery = z.object({});
```

---

## ステップ2: 検証ミドルウェア作成
**ファイル**: `src/lib/validation.ts` (新規)
```typescript
import { Context, Next } from 'hono';
import { z, ZodSchema, ZodError } from 'zod';
import { ValidationError } from './errors';

type SchemaMap = {
  body?: ZodSchema;
  params?: ZodSchema;
  query?: ZodSchema;
};

export function validate(schemas: SchemaMap) {
  return async (c: Context, next: Next) => {
    try {
      if (schemas.body) {
        const contentType = c.req.header('content-type') || '';
        let body: unknown;
        if (contentType.includes('multipart/form-data')) {
          body = await c.req.parseBody();
        } else if (contentType.includes('application/json')) {
          body = await c.req.json();
        } else {
          body = {};
        }
        c.set('validatedBody', schemas.body.parse(body));
      }

      if (schemas.params) {
        c.set('validatedParams', schemas.params.parse(c.req.param()));
      }

      if (schemas.query) {
        c.set('validatedQuery', schemas.query.parse(c.req.query()));
      }

      await next();
    } catch (err) {
      if (err instanceof ZodError) {
        const details = err.errors.map(e => ({
          path: e.path.join('.'),
          message: e.message,
          code: e.code,
        }));
        throw new ValidationError('Validation failed', details);
      }
      throw err;
    }
  };
}

// ヘルパー: 型安全な取得
export function getValidatedBody<T>(c: Context): T {
  return c.get('validatedBody') as T;
}
export function getValidatedParams<T>(c: Context): T {
  return c.get('validatedParams') as T;
}
export function getValidatedQuery<T>(c: Context): T {
  return c.get('validatedQuery') as T;
}
```

---

## ステップ3: ボディサイズ制限ミドルウェア
**ファイル**: `src/lib/body-limit.ts` (新規)
```typescript
import { Context, Next } from 'hono';

interface BodyLimitOptions {
  maxSize: number; // bytes
  errorMessage?: string;
}

export function bodyLimit({ maxSize, errorMessage = 'Request body too large' }: BodyLimitOptions) {
  return async (c: Context, next: Next) => {
    const contentLength = c.req.header('content-length');
    if (contentLength && parseInt(contentLength, 10) > maxSize) {
      return c.json({ error: errorMessage, maxSize }, 413);
    }
    await next();
  };
}
```

---

## ステップ4: 各ルートへの適用
**対象ファイル**: 全 `src/routes/*.ts`

**例 (upload.ts)**:
```typescript
import { validate, getValidatedBody } from '../lib/validation';
import { bodyLimit } from '../lib/body-limit';
import { uploadBody, fileIdParam } from '../lib/schemas';

export function registerUploadRoutes(app: Hono<{ Bindings: Env }>) {
  app.post('/api/upload',
    bodyLimit({ maxSize: 100 * 1024 * 1024 }), // 100MB
    validate({ body: uploadBody }),
    async (c) => {
      const body = getValidatedBody<{ file: File }>(c);
      // 以降、body.file は型安全
    }
  );

  app.get('/api/uploads',
    validate({ query: paginationQuery }),
    async (c) => { ... }
  );

  app.delete('/api/uploads/:fileId',
    validate({ params: fileIdParam }),
    async (c) => { ... }
  );
}
```

---

## ステップ5: ファイル名サニタイズ統一
**ファイル**: `src/lib/utils.ts` 修正
```typescript
export function sanitizeFilename(filename: string): string {
  // パストラバーサル防止
  const clean = filename.replace(/[\\/]/g, '_').replace(/\.\.+/g, '_');
  // 制御文字除去
  return clean.replace(/[\x00-\x1f\x7f]/g, '');
}

export function isValidFilename(filename: string): boolean {
  const sanitized = sanitizeFilename(filename);
  return sanitized === filename &&
    /^[a-zA-Z0-9._\-\u3000-\u9faf\u3040-\u309f\u30a0-\u30ff（）　]+\.pdf$/i.test(filename);
}
```

---

## ステップ6: バリデーションテスト作成
**ファイル**: `src/lib/__tests__/validation.test.ts` (新規)
- 正常系: 有効データでパス
- 異常系: 必須項目欠落、型不一致、範囲外、正規表現不一致
- FormData対応テスト（multipart）
- サイズ制限テスト（413返却確認）

---

## ステップ7: OpenAPIスキーマ連携
**ファイル**: `src/lib/openapi-schemas.ts` (新規)
- `@hono/zod-openapi` の `z.openapi()` でメタデータ付与
- 全スキーマに `description`, `example` 追加
- 自動生成されるOpenAPI仕様にバリデーションルール反映

---

## ステップ8: 既存手動バリデーション削除
- 全ルートから `if (!validateXxx(...))` 等の手動チェック削除
- `c.req.json().catch(() => ({}))` 等の暗黙的パース削除

---

## ステップ9: ドキュメント化
**ファイル**: `docs/api/validation.md` (新規)
- スキーマ定義ガイド
- 新エンドポイント追加時の手順
- エラーレスポンス形式仕様

---

## 完了条件
- [ ] 全エンドポイントでZodスキーマ検証適用
- [ ] 型安全な `getValidatedBody/Params/Query` 使用
- [ ] ボディサイズ制限が全ルートで動作
- [ ] テストで全バリデーションルール網羅
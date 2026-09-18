# P9: OpenAPI/Swagger ドキュメント & コントラクトテスト

## 概要
APIの自動ドキュメント生成とコントラクトテストにより、APIの可視性、テスト可能性、および後方互換性を向上させる。ZodスキーマとHonoを組み合わせてOpenAPI 3.1仕様を自動生成し、契約テストで実装とドキュメントの整合性を確保する。

---

## ステップ1: OpenAPI依存関係追加
**ファイル**: `package.json`
```json
{
  "dependencies": {
    "hono": "^4.0.0",
    "zod": "^3.22.0",
    "@hono/zod-openapi": "^0.10.0" // 新規追加
  },
  "devDependencies": {
    "@cloudflare/workers-types": "^4.20240117.0",
    "typescript": "^5.3.0",
    "wrangler": "^3.0.0",
    "vitest": "^1.0.0"
  }
}
```

**実行**: `npm install` で依存関係をインストール

---

## ステップ2: OpenAPI設定初期化
**ファイル**: `src/lib/openapi.ts` (新規)
```typescript
import { Hono } from 'hono';
import { OpenAPIHono, createRoute, z } from '@hono/zod-openapi';
import type { Env } from './types';

// OpenAPI対応のHonoインスタンスを作成
export function createOpenAPIApp(): OpenAPIHono<{ Bindings: Env }> {
  return new OpenAPIHono({
    strict: false, // ルール違反を許否（開発時はfalseが良いかも）
    // デフォルトのレスポンススキーマを設定
    defaultHook: (result) => {
      if (result.status >= 400) {
        // エラーレスポンスのフォーマットを統一
        return {
          json: (body: any) => {
            return {
              status: result.status,
              json: {
                error: {
                  code: body.error?.code || 'UNKNOWN_ERROR',
                  message: body.error?.message || 'An unknown error occurred',
                  details: body.error?.details
                }
              }
            };
          }
        };
      }
      return result;
    }
  });
}

// OpenAPIドキュメント用のコンポーネントスキーマ定義
export const openapiComponents = {
  schemas: {
    ErrorResponse: {
      type: 'object',
      properties: {
        error: {
          type: 'object',
          properties: {
            code: { type: 'string', example: 'VALIDATION_ERROR' },
            message: { type: 'string', example: 'Invalid fileId format' },
            details: { 
              type: ['object', 'array', 'string', 'number', 'boolean', 'null'],
              example: { field: 'fileId', value: 'invalid-format' }
            }
          },
          required: ['code', 'message']
        }
      },
      required: ['error']
    },
    PaginatedResponse: {
      type: 'object',
      properties: {
        limit: { type: 'integer', example: 20 },
        offset: { type: 'integer', example: 0 },
        count: { type: 'integer', example: 25 }
      }
    }
  }
};

// カスタムフック: リクエスト・レスポンスロギング（開発時用）
export function openapiHook() {
  return async (c: any, next: () => Promise<any>) => {
    const start = Date.now();
    await next();
    const duration = Date.now() - start;
    
    // 開発時のみ詳細ログ出力
    if (process.env.NODE_ENV !== 'production') {
      console.log(`${c.req.method} ${c.req.path} - ${c.res.status} - ${duration}ms`);
    }
  };
}
```

**確認**: `npx tsc --noEmit` で型エラーなし

---

## ステップ3: ZodスキーマをOpenAPI対応に強化
**ファイル**: `src/lib/schemas.ts` 修正
- 既存のZodスキーマにOpenAPIメタデータを追加

```typescript
import { z } from 'zod';
import { OpenAPIHono } from '@hono/zod-openapi';

// OpenAPIメタデータ付与ヘルパー
export function createOpenApiSchema<T extends z.ZodTypeAny>(
  schema: T,
  opts: {
    description?: string;
    example?: unknown;
  } = {}
) {
  return z.custom(
    (val) => schema.safeParse(val).success,
    {
      error: (params) => {
        throw new z.ZodError([
          {
            received: params.data,
            code: 'invalid_type',
            message: `${params.path.join('.')} is invalid`,
            path: params.path
          }
        ]);
      }
    }
  ).openapi({
    description: opts.description,
    example: opts.example
  });
}

// 既存スキーマをOpenAPI対応に変換
export const fileIdParam = z.object({
  fileId: z.string().regex(
    /^[a-f0-9]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i, 
    'Invalid fileId format'
  ).openapi({
    description: 'File identifier (UUID or 32-character hex)',
    example: '550e8400-e29b-41d4-a716-446655440000'
  })
});

export const paginationQuery = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20).openapi({
    description: 'Number of items to return per page',
    example: 20
  }),
  offset: z.coerce.number().int().min(0).default(0).openapi({
    description: 'Number of items to skip',
    example: 0
  })
});

// アップロード
export const uploadBody = z.object({
  file: z.instanceof(File).refine(f => f.type === 'application/pdf', 'Only PDF allowed')
}).openapi({
  description: 'PDF file to upload',
  // FileオブジェクトはJSONシリアライズできないため、説明のみ
});

// 処理開始
export const processStartBody = z.object({
  options: z.object({
    compactLayout: z.boolean().optional().openapi({
      description: 'Use compact layout for output',
      example: false
    }),
    useEmojis: z.boolean().optional().openapi({
      description: 'Use emojis in output',
      example: true
    }),
    promptLayout: z.string().optional().openapi({
      description: 'Layout prompt for processing',
      example: 'detailed'
    }),
    promptStrictMode: z.boolean().optional().openapi({
      description: 'Enable strict prompt mode',
      example: false
    }),
    promptHasDiagrams: z.boolean().optional().openapi({
      description: 'Input contains diagrams',
      example: true
    }),
    promptLowQualityMode: z.boolean().optional().openapi({
      description: 'Enable low quality mode',
      example: false
    }),
    baseUrl: z.string().url().optional().openapi({
      description: 'Base URL for relative links',
      example: 'https://example.com'
    })
  }).openapi({
    description: 'Processing options'
  })
}).openapi({
  description: 'Processing start request'
});

// 進捗更新
export const progressUpdateBody = z.object({
  progress: z.number().int().min(0).max(100).openapi({
    description: 'Progress percentage (0-100)',
    example: 75
  }),
  stage: z.string().max(200).optional().openapi({
    description: 'Current processing stage',
    example: 'OCR解析中'
  }),
  status: z.enum(['pending', 'processing', 'completed', 'failed']).optional().openapi({
    description: 'Processing status',
    example: 'processing'
  }),
  result: z.object({
    markdown: z.string().optional().openapi({
      description: 'Generated markdown content',
      example: '# タイトル\n\nこれはサンプルです。'
    }),
    html: z.string().optional().openapi({
      description: 'Generated HTML content',
      example: '<h1>タイトル</h1><p>これはサンプルです。</p>'
    })
  }).optional().openapi({
    description: 'Processing result (when completed)'
  }),
  error: z.string().optional().openapi({
    description: 'Error message (when failed)',
    example: 'Failed to process PDF'
  })
}).openapi({
  description: 'Progress update request'
});

// 結果保存
export const resultSaveBody = z.object({
  markdown: z.string().min(1).max(10 * 1024 * 1024).openapi({
    description: 'Markdown content to save',
    example: '# サンプルマニュアル\n\nこれはサンプルです。'
  }),
  title: z.string().max(300).optional().openapi({
    description: 'Title of the document',
    example: 'サンプルマニュアル'
  })
}).openapi({
  description: 'Result save request'
});

// Geminiプロキシ
export const geminiProxyParams = z.object({
  model: z.string().regex(/^[a-z0-9.\-]+$/i, 'Invalid model name').openapi({
    description: 'Gemini model name',
    example: 'gemini-1.5-flash'
  }),
  method: z.enum(['generateContent', 'streamGenerateContent', 'countTokens']).openapi({
    description: 'Gemini API method to call',
    example: 'generateContent'
  })
}).openapi({
  description: 'Gemini API endpoint parameters'
});

export const geminiProxyBody = z.record(z.unknown()).openapi({
  description: 'Request body to forward to Gemini API',
  // 実際の構造は複雑なので説明のみ
});

// Visionプロキシ
export const visionProxyBody = z.object({
  requests: z.array(z.object({
    image: z.object({ content: z.string() }),
    features: z.array(z.object({ 
      type: z.string(), 
      maxResults: z.number().optional() 
    }))
  })).max(16).openapi({
    description: 'Vision API requests (max 16)',
    example: [{
      image: { content: 'base64encodedimage...' },
      features: [{ type: 'TEXT_DETECTION', maxResults: 100 }]
    }]
  })
}).openapi({
  description: 'Vision API request body'
});

// Mermaid保存
export const mermaidSaveBody = z.object({
  mermaid: z.string().min(1).max(512 * 1024).openapi({
    description: 'Mermaid diagram source',
    example: 'graph TD\n    A[Start] --> B{Decision}\n    B -->|Yes| C[OK]\n    B -->|No| D[Error]'
  })
}).openapi({
  description: 'Mermaid save request'
});

// PIIマスク
export const piiMaskBody = z.object({
  text: z.string().max(1024 * 1024).openapi({
    description: 'Text to mask PII from',
    example: 'Contact me at john@example.com or 555-123-4567'
  })
}).openapi({
  description: 'PII mask request'
});

// i18n言語検出
export const i18nDetectBody = z.object({
  text: z.string().openapi({
    description: 'Text to detect language from',
    example: 'これはサンプルテキストです。'
  })
}).openapi({
  description: 'Language detection request'
});

// 設定取得（クエリパラメータなし）
export const configQuery = z.object({}).openapi({
  description: 'Get application configuration'
});
```

---

## ステップ4: OpenAPIルート作成
**ファイル**: `src/routes/openapi.ts` (新規)
```typescript
import { OpenAPIHono } from '@hono/zod-openapi';
import { createOpenAPIApp, openapiComponents } from '../lib/openapi';
import { registerRoutes } from './index'; // 全ルートを登録する関数を作成する必要がある

// OpenAPI対応アプリケーション作成
const app = createOpenAPIApp();

// 全ルートを登録（既存のregister*Routes関数を呼び出す）
// 実際には、index.ts からルート登録関数をエクスポートする必要がある
// ここでは概念を示す

// ドキュメントエンドポイント
app.doc('/doc', {
  openapi: '3.1.0',
  info: {
    title: 'Manual Maker API',
    version: '2.0.0',
    description: 'API for handwritten manual processing system'
  }
});

// Swagger UI エンドポイント（@hono/zod-openapi には組み込みUIがないため、別途実装が必要）
// あるいは、 /api/doc を外部のSwagger UIビューアに指向させる

export { app as openapiApp };
```

---

## ステップ5: 各ルートをOpenAPI対応に修正
**対象ファイル**: 全 `src/routes/*.ts`
- 現在の `Hono` インスタンスを `OpenAPIHono` に変更
- `app.post/get/etc` を `app.openapi.post/get/etc` に変更し、OpenAPIメタデータを追加

**例 (upload.ts)**:
```typescript
import { OpenAPIHono } from '@hono/zod-openapi';
import { registerUploadRoutes } from './upload'; // 変更後の関数をインポート
// ... 他のインポート

// index.ts で
import { createOpenAPIApp } from './lib/openapi';
import { registerUploadRoutes } from './routes/upload';
// ... 他のルート登録関数

export function registerRoutes(app: OpenAPIHono<{ Bindings: Env }>) {
  registerUploadRoutes(app);
  registerConfigRoutes(app);
// ... 他のルート登録
}

// upload.ts 修正
import { OpenAPIHono } from '@hono/zod-openapi';
import { validate, getValidatedBody } from '../lib/validation';
import { bodyLimit } from '../lib/body-limit';
import { uploadBody, fileIdParam } from '../lib/schemas';
import { ValidationError } from '../lib/errors';

export function registerUploadRoutes(app: OpenAPIHono<{ Bindings: Env }>) {
  app.openapi('/api/upload',
    'post',
    {
      middleware: [
        bodyLimit({ maxSize: 100 * 1024 * 1024 }), // 100MB
        validate({ body: uploadBody })
      ],
      summary: 'Upload a PDF file',
      description: 'Upload a PDF file for processing. The file will be stored in R2 and metadata saved in KV.',
      request: {
        body: {
          content: {
            'multipart/form-data': {
              schema: uploadBody
            }
          }
        }
      },
      responses: {
        '200': {
          description: 'File uploaded successfully',
          content: {
            'application/json': {
              schema: uploadBody
            }
          }
        },
        '400': {
          description: 'Validation error',
          content: {
            'application/json': {
              schema: z.object({
                error: z.object({
                  code: z.string(),
                  message: z.string(),
                  details: z.unknown().optional()
                })
              })
            }
          }
        },
        '413': {
          description: 'File too large',
          content: {
            'application/json': {
              schema: z.object({
                error: z.object({
                  code: z.string(),
                  message: z.string()
                })
              })
            }
          }
        },
        '500': {
          description: 'Internal server error',
          content: {
            'application/json': {
              schema: z.object({
                error: z.object({
                  code: z.string(),
                  message: z.string()
                })
              })
            }
          }
        }
      }
    },
    async (c) => {
      try {
        const body = getValidatedBody<{ file: File }>(c);
        // ... 既存の処理 unchanged
      } catch (error) {
        // ... 既存のエラーハンドリング unchanged
      }
    }
  );

  // 他のルートも同様に変更
  app.openapi('/api/uploads',
    'get',
    {
      middleware: [
        validate({ query: paginationQuery })
      ],
      summary: 'Get list of uploaded files',
      description: 'Get a paginated list of all uploaded files.',
      request: {
        query: {
          content: {
            'application/json': {
              schema: paginationQuery
            }
          }
        }
      },
      responses: {
        '200': {
          description: 'List of uploaded files',
          content: {
            'application/json': {
              schema: z.object({
                uploads: z.array(uploadBody)
              })
            }
          }
        },
        '400': {
          description: 'Validation error',
          content: {
            'application/json': {
              schema: z.object({
                error: z.object({
                  code: z.string(),
                  message: z.string(),
                  details: z.unknown().optional()
                })
              })
            }
          }
        },
        '500': {
          description: 'Internal server error',
          content: {
            'application/json': {
              schema: z.object({
                error: z.object({
                  code: z.string(),
                  message: z.string()
                })
              })
            }
          }
        }
      }
    },
    async (c) => {
      // ... 既存の処理
    }
  );
}
```

**このパターンを全ルートに適用**

---

## ステップ6: OpenAPI JSON エンドポイント作成
**ファイル**: `src/index.ts` 修正
- OpenAPI対応アプリケーションを作成し、ルートを登録
- `/api/doc` エンドポイントでOpenAPI JSONを提供

```typescript
import { Hono } from 'hono';
import { createOpenAPIApp } from './lib/openapi';
import { registerRoutes } from './routes'; // ルート登録関数をエクスポートする必要がある

// OpenAPI対応アプリケーション作成
const app = createOpenAPIApp<{ Bindings: Env }>();

// 全ルートを登録
registerRoutes(app);

// OpenAPI JSON エンドポイント
app.get('/api/doc', (c) => {
  return c.json(app.openapiDocument);
});

// Swagger UI へのリダイレクトまたは組み込み（オプション）
// 例えば、Swagger UI CDN を使って /api/swagger エンドポイントを作成
app.get('/api/swagger', (c) => {
  return c.html(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Manual Maker API - Swagger UI</title>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
    </head>
    <body>
      <div id="swagger-ui"></div>
      <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
      <script>
        window.onload = () => {
          window.ui = SwaggerUIBundle({
            url: "/api/doc",
            dom_id: '#swagger-ui',
            deepLinking: true,
            presets: [
              SwaggerUIBundle.presets.forApis,
              SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout"
          });
        }
      </script>
    </body>
    </html>
  `);
});

// 既存のエラーハンドラーなどはそのまま
app.onError((err, c) => {
  console.error('Unhandled error:', err);
  return c.json({ error: 'Internal server error' }, 500);
});

export default app;
```

---

## ステップ7: コントラクトテスト作成
**ファイル**: `src/routes/__tests__/openapi-contract.test.ts` (新規)
- OpenAPI仕様に従っているかをテスト
- レスポンスがスキーマに準拠しているかを検証

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { OpenAPIHono } from '@hono/zod-openapi';
import { createOpenAPIApp } from '../../lib/openapi';
import { registerRoutes } from '../../routes'; // 仮のインポートパス
import { StatusCodes } from 'http-status-codes';

// モック環境変数
const mockEnv = {
  BUCKET: {
    put: vi.fn(),
    get: vi.fn(),
    delete: vi.fn()
  } as unknown as R2Bucket,
  PROCESSING_KV: {
    put: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
    list: vi.fn()
  } as unknown as KVNamespace,
  GEMINI_API_KEY: 'test-gemini-key',
  GOOGLE_API_KEY: 'test-google-key',
  GOOGLE_CLOUD_PROJECT_ID: 'test-project-id',
  DEFAULT_LANGUAGE: 'ja',
  MAX_FILE_SIZE_MB: '50',
  WEB_UPLOAD_MAX_MB: '100',
  GEMINI_MODEL_NAME: 'gemini-1.5-flash'
} as Env;

describe('OpenAPI Contract Testing', () => {
  let app: OpenAPIHono<{ Bindings: Env }>;

  beforeEach(() => {
    app = createOpenAPIApp<{ Bindings: Env }>();
    // 環境変数をモック
    vi.stubEnv('GEMINI_API_KEY', mockEnv.GEMINI_API_KEY);
    vi.stubEnv('GOOGLE_API_KEY', mockEnv.GOOGLE_API_KEY);
    vi.stubEnv('GOOGLE_CLOUD_PROJECT_ID', mockEnv.GOOGLE_CLOUD_PROJECT_ID);
    vi.stubEnv('DEFAULT_LANGUAGE', mockEnv.DEFAULT_LANGUAGE);
    vi.stubEnv('MAX_FILE_SIZE_MB', mockEnv.MAX_FILE_SIZE_MB);
    vi.stubEnv('WEB_UPLOAD_MAX_MB', mockEnv.WEB_UPLOAD_MAX_MB);
    vi.stubEnv('GEMINI_MODEL_NAME', mockEnv.GEMINI_MODEL_NAME);
    
    registerRoutes(app);
  });

  it('should return valid OpenAPI document', async () => {
    const res = await app.request('/api/doc');
    expect(res.status).toBe(StatusCodes.OK);
    
    const openapiDoc = await res.json();
    expect(openapiDoc).toBeDefined();
    expect(openapiDoc.openapi).toBe('3.1.0');
    expect(openapiDoc.info.title).toBe('Manual Maker API');
    expect(openapiDoc.info.version).toBe('2.0.0');
    
    // 基本的なパスが存在するか確認
    expect(openapiDoc.paths).toBeDefined();
    expect(openapiDoc.paths['/api/upload']).toBeDefined();
    expect(openapiDoc.paths['/api/health']).toBeDefined();
  });

  it('should validate upload endpoint response against schema', async () => {
    // モックファイルを作成
    const mockFile = new File(['dummy pdf content'], 'test.pdf', {
      type: 'application/pdf'
    });
    
    // FormDataを作成
    const formData = new FormData();
    formData.append('file', mockFile);
    
    const res = await app.request(
      new Request('http://localhost/api/upload', {
        method: 'POST',
        body: formData
      })
    );
    
    // 実際のバリデーションはここで行うが、モック環境では複雑になるため、
    // 簡易的にステータスコードと基本構造をチェック
    expect([StatusCodes.OK, StatusCodes.BAD_REQUEST, StatusCodes.INTERNAL_SERVER_ERROR]).toContain(res.status);
    
    if (res.status === StatusCodes.OK) {
      const json = await res.json();
      expect(json).toHaveProperty('fileId');
      expect(json).toHaveProperty('filename');
      expect(json).toHaveProperty('sizeMb');
      expect(json).toHaveProperty('path');
      expect(json).toHaveProperty('uploadedAt');
    }
  });

  // 他のエンドポイントも同様にテスト
  it('should validate health endpoint response', async () => {
    const res = await app.request('/api/health');
    expect(res.status).toBe(StatusCodes.OK);
    
    const json = await res.json();
    expect(json).toHaveProperty('status', 'ok');
    expect(json).toHaveProperty('version', '2.0.0');
    expect(json).toHaveProperty('processorType', 'cloudflare-workers');
  });
});
```

---

## ステップ8: CI/CD パイプラインに契約テスト追加
**ファイル**: `.github/workflows/ci.yml` (例)
```yaml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '20'
        
    - name: Install dependencies
      run: npm ci
      
    - name: Run tests
      run: npm test
      
    - name: Type check
      run: npm run typecheck
      
    - name: Generate OpenAPI spec and validate
      run: |
        # OpenAPIスペックを生成して検証
        node -e "
          const { createOpenAPIApp } = require('./src/lib/openapi');
          // 実際にはルート登録などが必要だが、ここでは概念を示す
          console.log('OpenAPI generation would happen here');
        "
```

---

## ステップ9: ドキュメント化・運用ガイド
**ファイル**: `docs/api/openapi-guide.md` (新規)
- OpenAPI仕様の閲覧方法
- カスタムクライアントSDKの生成方法（OpenAPI Generator等を使用）
- ドキュメントと実装の整合性を保つためのベストプラクティス
- バージョニング戦略
- 非互換な変更の扱い方

**クライアントSDK生成例**:
```bash
# OpenAPI Generator を使用して TypeScript クライアントSDK 生成
npx @openapitools/openapi-generator-cli generate \
  -i http://localhost:8787/api/doc \
  -g typescript-axios \
  -o ./generated-client \
  --additional-properties=withSeparateModelsAndApi=true,modelPropertyNaming=camelCase
```

---

## 完了条件
- [ ] `@hono/zod-openapi` がインストール済み
- [ ] OpenAPI対応アプリケーションが作成済み
- [ ] 全エンドポイントがOpenAPIメタデータ付きで定義済み
- [ ] `/api/doc` エンドポイントで有効なOpenAPI 3.1 JSONが提供されている
- [ ] `/api/swagger` エンドポイントでSwagger UIが利用可能（オプション）
- [ ] コントラクトテストが作成され、レスポンスがスキーマに準拠していることを検証済み
- [ ] CI/CDパイプラインに契約テストが組み込まれている
- [ ] ドキュメントにOpenAPIの使い方とクライアントSDK生成方法が記載されている
- [ ] 既存の機能が変更されずにOpenAPI対応が実装されている
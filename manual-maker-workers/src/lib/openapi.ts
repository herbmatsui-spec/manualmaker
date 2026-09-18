import { Hono } from 'hono';
import { OpenAPIHono, createRoute, z } from '@hono/zod-openapi';
import type { Env } from './types';

// OpenAPI対応のHonoインスタンスを作成
export function createOpenAPIApp(): OpenAPIHono<{ Bindings: Env }> {
  return new OpenAPIHono({
    strict: false, // ルール違反を許否（開発時はfalseが良いかも）
    // デフォルトのレスポンススキーマを設定
    defaultHook: (result, c) => {
      if (result.success === false) {
        // バリデーションエラーの場合、統一フォーマットでレスポンスを返す
        const firstError = result.error.issues[0];
        return c.json(
          {
            error: {
              code: firstError.code ?? 'VALIDATION_ERROR',
              message: firstError.message ?? 'Invalid input',
            }
          },
          400
        );
      }
      // 成功時は void を返してデフォルトの挙動を任せる
      return void 0;
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
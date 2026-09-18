# バリデーションシステム ドキュメント

## スキーマ定義ガイド

このプロジェクトでは、入力バリデーションにZodスキーマを使用しています。以下はスキーマ定義のベストプラクティスです。

### 基本スキーマ定義

```typescript
import { z } from 'zod';

// パラメータスキーマ
export const fileIdParam = z.object({
  fileId: z.string().regex(
    /^[a-f0-9]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i, 
    'Invalid fileId format'
  ).openapi({
    description: 'File identifier (UUID or 32-character hex)',
    example: '550e8400-e29b-41d4-a716-446655440000'
  })
});

// リクエストボディスキーマ
export const uploadBody = z.object({
  file: z.instanceof(File).refine(f => f.type === 'application/pdf', 'Only PDF allowed')
}).openapi({
  description: 'PDF file to upload',
  // FileオブジェクトはJSONシリアライズできないため、説明のみ
}).passthrough(); // FormData対応
```

### OpenAPIメタデータの付与

スキーマにOpenAPIメタデータを付与することで、自動生成されるAPIドキュメントに詳細情報を含めることができます:

```typescript
export const openapiFileIdParam = fileIdParam.openapi({
  description: 'Unique file identifier (UUID or 32-character hex)',
  example: { fileId: '550e8400-e29b-41d4-a716-446655440000' }
});
```

### 一般的なバリデーションパターン

1. **文字列バリデーション**
   ```typescript
   z.string().min(1, 'Required field').max(100, 'Too long')
   ```

2. **数値バリデーション**
   ```typescript
   z.number().int().min(0).max(100)
   ```

3. **列挙型バリデーション**
   ```typescript
   z.enum(['pending', 'processing', 'completed', 'failed'])
   ```

4. **オブジェクトバリデーション**
   ```typescript
   z.object({
     name: z.string(),
     age: z.number().int().positive()
   })
   ```

5. **配列バリデーション**
   ```typescript
   z.array(z.string()).max(10, 'Too many items')
   ```

## 新エンドポイント追加時の手順

新しいエンドポイントを追加する際は、以下の手順に従って一貫したバリデーションを適用してください。

### 1. スキーマの定義またはインポート

`src/lib/schemas.ts` に適切なスキーマを定義するか、既存のスキーマをインポートします:

```typescript
import { z } from 'zod';

// 新しいスキーマを定義
export const newEndpointSchema = z.object({
  // スキーマ定義
});

// または既存のスキーマをインポート
// import { existingSchema } from './schemas';
```

### 2. OpenAPIスキーマの準備（オプションだが推奨）

`src/lib/openapi-schemas.ts` にOpenAPIメタデータ付きスキーマを追加します:

```typescript
import { newEndpointSchema } from './schemas';
export const openapiNewEndpointSchema = newEndpointSchema.openapi({
  description: 'Description of the schema',
  example: { /* example data */ }
});
```

### 3. ルートハンドラーへの実装

ルートファイル（`src/routes/*.ts`）で以下のように実装します:

```typescript
import { Hono } from 'hono';
import { validate, getValidatedBody, getValidatedParams } from '../lib/validation';
// OpenAPIスキーマを使用する場合
// import { openapiNewEndpointSchema } from '../lib/openapi-schemas';
// または通常のスキーマを使用する場合
// import { newEndpointSchema } from '../lib/schemas';

export function registerNewEndpointRoutes(app: Hono<AppEnv>) {
  app.post('/api/new-endpoint',
    // ボディサイズ制限が必要な場合（オプション）
    // bodyLimit({ maxSize: 10 * 1024 * 1024 }), // 10MB example
    
    // バリデーションの適用
    validate({
      // params: openapiNewEndpointParamSchema, // パラメータがある場合
      body: openapiNewEndpointSchema // または newEndpointSchema
    }),
    async (c) => {
      // 型安全な値の取得
      const data = getValidatedBody<YourDataType>(c);
      
      // ビジネスロジックの実装
      // ...
      
      return c.json(result);
    }
  );
}
```

### 4. エラーハンドリング

バリデーションエラーは自動的に`ValidationError`としてスローされ、エラーハンドラーマiddlewareによって適切なHTTPレスポンス（400 Bad Request）に変換されます。

カスタムエラーハンドリングが必要な場合は、ルートレベルで設定できます:

```typescript
app.onError((error, c) => {
  if (error instanceof ValidationError) {
    return c.json({ error: error.code, details: error.details }, 400);
  }
  // その他のエラーハンドリング
});
```

## エラーレスポンス形式仕様

バリデーションに失敗した場合、以下の形式でエラーレスポンスが返却されます。

### バリデーションエラー (400 Bad Request)

```json
{
  "error": "VALIDATION_ERROR",
  "details": [
    {
      "path": "field.name",
      "message": "Error message",
      "code": "invalid_type",
      "expected": "string",
      "received": "undefined"
    }
  ]
}
```

#### フィールド説明:
- `error`: エラーコード（常に "VALIDATION_ERROR"）
- `details`: エラー詳細の配列
  - `path`: エラーが発生したフィールドのパス（ドット記法）
  - `message`: ユーザー向けのエラーメッセージ
  - `code`: Zodエラーコード（invalid_type, invalid_literal, invalid_union, invalid_args, invalid_return_type, invalid_date, invalid_string, too_big, too_small, invalid_literal, unrecognized_keys, invalid_intersection_types, not_multiple_of, not_finite, invalid_int, invalid_date, invalid_string, etc.）
  - `expected`: 期待される型や値（オプション）
  - `received`: 実際に受け取った型や値（オプション）

### 例: 必須フィールド欠落

```json
{
  "error": "VALIDATION_ERROR",
  "details": [
    {
      "path": "email",
      "message": "Required",
      "code": "invalid_type",
      "expected": "string",
      "received": "undefined"
    }
  ]
}
```

### 例: 型不一致

```json
{
  "error": "VALIDATION_ERROR",
  "details": [
    {
      "path": "age",
      "message": "Expected number, received string",
      "code": "invalid_type",
      "expected": "number",
      "received": "string"
    }
  ]
}
```

### 例: 範囲外バリデーション

```json
{
  "error": "VALIDATION_ERROR",
  "details": [
    {
      "path": "score",
      "message": "Number must be less than or equal to 100",
      "code": "too_big",
      "maximum": 100,
      "type": "number",
      "inclusive": true,
      "exact": true,
      "received": 150
    }
  ]
}
```

### ボディサイズ制限エラー (413 Payload Too Large)

リクエストボディがサイズ制限を超えた場合:

```json
{
  "error": "Request body too large",
  "maxSize": 10485760
}
```

#### フィールド説明:
- `error`: エラーメッセージ
- `maxSize`: 許可される最大バイト数

## ベストプラクティス

1. **スキーマの再利用可能性**: 同様のデータ構造はスキーマを再利用してDRY原则を遵守
2. **段階的バリデーション**: 複雑なスキーマは小さなスキーマに分解して組み合わせる
3. **エラーメッセージのユーザーフレンドリー化**: エンドユーザーにわかりやすいメッセージを提供
4. **セキュリティ考慮**: 入力サイズ、型、形式を厳密にバリデーションしてインジェクション攻撃を防止
5. **ドキュメントの最新状態維持**: スキーマを変更したらOpenAPIメタデータも同時に更新

## トラブルシューティング

### Q: バリデーションが通らないが、なぜかわからない
A: ペイロードの内容を確認し、スキーマ定義と一致しているかチェックしてください。特に型と形式に注意してください。

### Q: FormDataが正しくパースされない
A: `Content-Type: multipart/form-data` ヘッダーが正しく設定されているか確認してください。また、ファイルサイズ制限も確認してください。

### Q: OpenAPIドキュメントにバリデーションルールが反映されない
A: `openapi-schemas.ts` を正しくインポートし、`openapi` メソッドを適用しているか確認してください。

## 関連ファイル

- `src/lib/validation.ts`: バリデーションミドルウェアの実装
- `src/lib/schemas.ts`: 基本Zodスキーマ定義
- `src/lib/openapi-schemas.ts`: OpenAPIメタデータ付きスキーマ
- `src/lib/body-limit.ts`: ボディサイズ制限ミドルウェア
- `src/lib/__tests__/validation.test.ts`: バリデーションテスト
- `src/routes/*.ts`: 実際のエンドポイント実装例
# バリデーションシステム ドキュメント

## 概要

Manual Makerのバリデーションシステムは、Zodライブラリを使用してリクエストのバリデーションを一元管理しています。これにより、バリデーションロジックの一貫性と保守性が向上しています。

## スキーマ定義ガイド

すべてのバリデーションスキーマは `src/lib/schemas.ts` に定義されています。

### 共通パラメータ

- **fileIdParam**: ファイルIDのバリデーション（UUIDまたは32文字のhex）
- **paginationQuery**: ページネーションパラメータ（limit, offset）

### エンドポイント固有スキーマ

各エンドポイントには専用のスキーマが定義されています：

- **uploadBody**: PDFファイルアップロードのバリデーション
- **processStartBody**: 処理開始時のオプションバリデーション
- **progressUpdateBody**: 処理進捗更新のバリデーション
- **resultSaveBody**: 処理結果保存のバリデーション
- **geminiProxyParams / geminiProxyBody**: Gemini APIプロキシのバリデーション
- **visionProxyBody**: Vision APIプロキシのバリデーション
- **mermaidSaveBody**: Mermaid図形保存のバリデーション
- **piiMaskBody**: PIIマスキングのバリデーション
- **i18nDetectBody**: 言語検出のバリデーション
- **configQuery**: 設定取得のバリデーション（パラメータなし）

### OpenAPI統合

`src/lib/openapi-schemas.ts` では、ZodスキーマにOpenAPIメタデータ（description, example）を追加し、自動生成されるOpenAPI仕様にバリデーションルールを反映しています。

## 新エンドポイント追加時の手順

1. **スキーマを定義**
   - `src/lib/schemas.ts` に新しいスキーマを追加する
   - 必要に応じて `src/lib/openapi-schemas.ts` にOpenAPIメタデータを追加する

2. **バリデーションミドルウェアを適用**
   - エンドポイントハンドラーに `validate()` ミドルウェアを追加する
   - バリデーション対象（body, params, query）を指定する
   - 例: `validate({ body: mySchema, params: idParam })`

3. **バリデーション済みデータを取得**
   - ハンドラー内で `getValidatedBody()`, `getValidatedParams()`, `getValidatedQuery()` ヘルパー関数を使用する
   - これらの関数は型安全な値を返す
   - 例: `const { fileId } = getValidatedParams<{ fileId: string }>(c);`

4. **エラーハンドリング**
   - バリデーション失敗時は自動的に `ValidationError` がスローされる
   - グローバルエラーハンドラーがこれを適切なJSONレスポンスに変換する

## エラーレスポンス形式仕様

バリデーション失敗時のエラーレスポンスは以下の形式です：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      {
        "path": "フィールドのパス（ドット区切り）",
        "message": "具体的なエラーメッセージ",
        "code": "Zodエラーコード"
      }
    ]
  }
}
```

### 例: 無効なfileIdの場合

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      {
        "path": "fileId",
        "message": "Invalid fileId format",
        "code": "invalid_string"
      }
    ]
  }
}
```

### 例: 必須フィールドが欠落している場合

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      {
        "path": "markdown",
        "message": "Required",
        "code": "invalid_type"
      }
    ]
  }
}
```

## ベストプラクティス

1. **スキーマはできるだけ具体的に** - 許容される値の範囲を狭く定義する
2. **ビジネスロジックはスキーマに含めない** - スキーマはデータの形式と基本的な制約のみをチェックする
3. **エラーメッセージはユーザーフレンドリーに** - 開発者向けの技術的詳細よりも、ユーザーが理解できるメッセージを心がける
4. **定期的にスキーマを見直す** - APIの変更に合わせてスキーマを更新する
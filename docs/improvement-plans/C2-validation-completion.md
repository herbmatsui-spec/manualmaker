# C2: Zodスキーマによる入力検証の完成

## 概要
P2で実装された基盤（Zodスキーマ・検証ミドルウェア・ボディサイズ制限）を基に、全エンドポイントでの一貫した検証適用、FormData対応の徹底、サイズ制限の特定ルート適用、テスト・ドキュメント化を完了する。

---

## ステップ1: 全ルートへのZodスキーマ検証適用
**対象ファイル**: 全 `src/routes/*.ts`
- `import { validate, getValidatedBody, getValidatedParams, getValidatedQuery } from '../lib/validation';`
- 各ルートハンドラーの先頭に `validate({ body: ..., params: ..., query: ... })` を追加
- ハンドラー内では `getValidatedBody<T>(c)` 等の型安全取得関数を使用

## ステップ2: 手動バリデーションの削除
**対象ファイル**: 全 `src/routes/*.ts`
- `if (!validateXxx(...))` 等の手動チェックをすべて削除
- `c.req.json().catch(() => ({}))` 等の暗黙的パースを削除し、検証ミドルウェアに委任

## ステップ3: ボディサイズ制限の特定ルート適用
**対象ファイル**: アップロード関連ルート（upload.ts, gemini.ts, vision.ts 等）
- `import { bodyLimit } from '../lib/body-limit';`
- 大容量ファイルを扱うエンドポイントに適切な `bodyLimit({ maxSize: ... })` を適用（例: アップロードは 100MB, Gemini/Vision プロキシは 10MB 等）

## ステップ4: FormData対応の徹底
**ファイル**: `src/lib/validation.ts`
- マルチパート/form-data の解析を `c.req.parseBody()` で正しく行い、`z.object({ file: z.instanceof(File) })` スキーマで検証
- `getValidatedBody` で取得した値が型安全であることを確認

## ステップ5: ファイル名サニタイズの統一適用
**対象ファイル**: ファイル名を扱う全ルート（upload.ts, process.ts, results.ts 等）
- `import { sanitizeFilename, isValidFilename } from '../lib/utils';`
- アップロード時のファイル名検証に `isValidFilename` を使用し、サニタイズは `sanitizeFilename` で行う

## ステップ6: OpenAPIスキーマ連携の完成
**ファイル**: `src/lib/openapi-schemas.ts`（既存）をルートに組み込み
- 全エンドポイントのリクエスト/レスポンススキーマに `openapi` メタデータ付与スキーマを使用
- `/api/doc` エンドポイントで生成されるOpenAPI仕様にバリデーションルールが正しく反映されることを確認

## ステップ7: バリデーションテストの作成・実行
**ファイル**: `src/lib/__tests__/validation.test.ts` (新規または既存を拡張)
- 正常系: 有効データでパス
- 異常系: 必須項目欠落、型不一致、範囲外、正規表現不一致
- FormData対応テスト（multipart）
- サイズ制限テスト（413返却確認）
- テストを実行し、カバレッジを向上

## ステップ8: ドキュメント化
**ファイル**: `docs/api/validation.md` (新規)
- スキーマ定義ガイド
- 新エンドポイント追加時の手順
- エラーレスポンス形式仕様

## ステップ9: 完了条件確認
- [ ] 全エンドポイントでZodスキーマ検証が適用されている
- [ ] 型安全な `getValidatedBody/Params/Query` が使用されている
- [ ] ボディサイズ制限が適切なルートで動作している（413エラー返却）
- [ ] テストで全バリデーションルールが網羅されている
- [ ] OpenAPI仕様にバリデーションルールが反映されている
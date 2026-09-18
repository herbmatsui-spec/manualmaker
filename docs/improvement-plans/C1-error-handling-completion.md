# C1: 構造化エラーハンドリングの完成（エラーコード・相関ID・ログ・メトリクス）

## 概要
P1で実装された基盤（エラークラス・相関IDミドルウェア・リトライロジック）を基に、全ルートでの統一エラーハンドリング、構造化ログ、メトリクス収集、ドキュメント化を完了する。

---

## ステップ1: エラーハンドリングミドルウェアの徹底適用
**対象ファイル**: `src/index.ts`
- `app.use('*', correlationId(), errorHandler())` をグローバルミドルウェアとして登録し、全ルートで相関ID付与と統一エラーレスポンスを適用
- 既存の `app.onError` は削除またはミドルウェアに統合（重複を避ける）

## ステップ2: 全ルートのエラーハンドリング統一
**対象ファイル**: 全 `src/routes/*.ts`
- 手動の `try-catch` 内で汎用 `Error` の代わりに専用エラークラス (`ValidationError`, `StorageError`, `ExternalAPIError` など) を投げる
- エラーログ出力時に `c.get('requestId')` を含める（例: `console.error(`[${c.get('requestId')}] Error:`, err)`）

## ステップ3: 構造化ログ実装
**ファイル**: `src/lib/logger.ts` (新規)
- `pino` 風軽量ロガーを実装（Cloudflare Workers 対応）
- JSON形式で `requestId`, `timestamp`, `level`, `message`, `context` を出力
- 本番環境では `wrangler tail --format json` と連携可能

## ステップ4: ロガーのミドルウェア組み込み
**ファイル**: `src/lib/logger.ts` にミドルウェア関数を追加
- リクエスト開始時にロガーインスタンスを作成し、コンテキストに保存
- エラーハンドラーからロガーを取得して構造化エラーログ出力

## ステップ5: エラーメトリクス収集
**ファイル**: `src/lib/metrics.ts` 実装
- エラー発生カウンター（エラーコード別、エンドポイント別、ステータスコード別）
- KV/R2/外部API別のレイテンシヒストグラム
- `/api/metrics` エンドポイントで Prometheus 形式出力

## ステップ6: メトリクスミドルウェア作成
**ファイル**: `src/lib/metrics-middleware.ts` (新規)
- リクエストレイテンシ測定、エラーカウントインクリメント
- グローバルに `app.use('*', metricsMiddleware())` として登録

## ステップ7: OpenAPIエラースキーマ定義
**ファイル**: `src/lib/openapi-errors.ts`（既存）をルートに組み込み
- `@hono/zod-openapi` 用エラーレスポンススキーマ定義
- 全エンドポイントの `responses` に共通エラー定義参照追加（`openapi.ts` または各ルートで）

## ステップ8: ドキュメント化・運用ガイド
**ファイル**: `docs/operational/error-handling.md` (新規)
- エラーコード一覧・対応フロー
- 相関IDを用いたログ追跡手順
- インシデント対応ランブック

## ステップ9: 完了条件確認
- [ ] 全エンドポイントが構造化エラー返却（ステータスコード・コード・相関ID・詳細含む）
- [ ] 相関IDがリクエスト/レスポンス/ログ全てに伝播
- [ ] 外部API障害時にリトライ→グレースフルデグレード動作
- [ ] テストカバレッジ 80% 以上（エラーハンドリング系テスト追加）
- [ ] 構造化ログがJSON形式で出力され、`wrangler tail` で確認可能
# C6: スライディングウィンドウ レート制限の完成

## 概要
P6で実装された基盤（レート制限アルゴリズム・ミドルウェア・一般的IPベース保護）を基に、特定ルートへの適切な制限適用、ヘダー・レスポンス強化、ホワイトリスト機能、メトリクス収集、テスト・ドキュメント化を完了する。

---

## ステップ1: 特定ルートへのレート制限適用
**対象ファイル**: 各ルートファイル
- アップロードルート (`src/routes/upload.ts`) に `import { rateLimitUpload } from '../lib/rate-limit-middleware';` を追加し、`app.post('/api/upload', rateLimitUpload(), ...)` を適用
- Geminiプロキシルート (`src/routes/gemini.ts`) に `import { rateLimitGeminiProxy } from '../lib/rate-limit-middleware';` を追加し、`app.post('/api/gemini/:model/:method', rateLimitGeminiProxy(), ...)` を適用
- Visionプロキシルート (`src/routes/vision.ts`) に `import { rateLimitVisionProxy } from '../lib/rate-limit-middleware';` を追加し、`app.post('/api/vision/annotate', rateLimitVisionProxy(), ...)` を適用
- 進捗更新ルート (`src/routes/process.ts`) に `import { rateLimitProgressUpdate } from '../lib/rate-limit-middleware';` を追加し、`app.put('/api/process/:fileId/progress', rateLimitProgressUpdate(), ...)` を適用（PUT エンドポイントが未実装なら作成）

## ステップ2: 一般的なIPベース保護の調整
**ファイル**: `src/index.ts`
- `app.use('*', rateLimitIPGeneral());` は残すが、特定ルートでより厳格な制限をかけているため、一般的な保護は緩めに設定（例: 1分間に150リクエスト）か、特定ルートで除外オプションを使用
- 除外したいルート（例: ヘルスチェック、メトリクス）には `rateLimitIPGeneral({ skipFailed: true })` またはパスベースでスキップする仕組みを検討

## ステップ3: ヘダー・レスポンス強化の確認
**ファイル**: `src/lib/rate-limit-middleware.ts`
- 既に実装済みの `Retry-After`, `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` ヘダーの追加が正常に機能していることをテストで確認
- 成功時にもヘダーを追加し、クライアント側での制御可能にしていることを確認

## ステップ4: 除外リスト・ホワイトリスト機能の適用
**ファイル**: `src/lib/rate-limiter.ts`
- `whitelist` オプションを使用して、特定IPやファイルIDのレート制限を除去する設定を追加
- **対象ファイル**: `src/index.ts` または特定ルートで、信頼できるサービス（例: 内部モニタリングサービスIP）や特定ファイルID（例: システム内部で使用する一時ファイル）をホワイトリストに追加
- 開発環境での自動除外（例: `127.0.0.1`, `::1`）を環境変数 `RATE_LIMIT_WHITELIST` から読み取る仕組みを実装

## ステップ5: レート制限状態モニタリングエンドポイントの実装
**ファイル**: `src/routes/metrics.ts`
- `/api/metrics/rate-limit` エンドポイントを実装し、レート制限関連の KV キーをサンプリングして統計出力
- 実際の本番環境では、レート制限ミドルウェア内でカウンターインクリメントを行い、KVまたは外部サービスにメトリクスを保存する仕組みを検討（プレースホルダーから本格実装へ）
- エンドポイントでは、過去1時間のリクエスト数、制限にかかった回数、現在のカウント等を返却

## ステップ6: テスト・シナリオの作成・実行
**ファイル**: `src/lib/__tests__/rate-limit.test.ts` (新規または既存を拡張)
- 正常系: 制限内リクエストは通過
- 境界値: 制限ちょうどで通過、1回超えで制限
- 時間経過: ウィンドウ推移後はリセット
- 複数キー: 異なるIP/fileIdは独立して制限
- ホワイトリスト: 指定キーは制限無視
- ヘダー返却: `Retry-After` 等が正常
- テストを実行し、カバレッジを向上

## ステップ7: ドキュメント化・運用ガイド
**ファイル**: `docs/operational/rate-limiting.md` (新規)
- レート限定の設計選択理由
- 各エンドポイント別推奨設定値（アップロード、Gemini/Visionプロキシ、進捗更新、一般IP保護）
- 監視とアラート設定ガイド
- 誤ってブロックされた場合の手動解除手順（KVキー削除）
- パフォーマンス影響評価
- 将来の改善方向（外部サービス連携等）

## ステップ8: 開発時無効化の確認
- 環境変数 `RATE_LIMIT_ENABLED=false` でレート制限が無効になることを確認（ミドルウェア内でのチェックが機能しているか）

## ステップ9: 完了条件確認
- [ ] レート制限ミドルウェアが実装済み
- [ ] アップロード、Gemini/Visionプロキシ、進捗更新に適切な制限が適用されている
- [ ] 一般的なIPベース保護がオプションで適用可能（かつ過剰制限を避ける調整済み）
- [ ] `429 Too Many Requests` と `Retry-After` ヘダーが正常返却
- [ ] テストで制限動作・ホワイトリスト・エラーケースが網羅されている
- [ ] ドキュメントに設定方法と運用ガイドが記載されている
- [ ] 開発時に環境変数で無効化可能 (`RATE_LIMIT_ENABLED=false`)
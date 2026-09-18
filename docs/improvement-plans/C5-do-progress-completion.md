# C5: Durable Objectsで進捗管理の完成（KVポーリング置換の完全実装）

## 概要
P5で実装された基盤（Durable Objects クラス、WebSocket エンドポイント、HTTP フォールバック）を基に、既存プロセスルートへの DO 連携、メトリクス収集、フォールバックメカニズムの強化、ドキュメント・ベンチマーク・テストを完了する。

---

## ステップ1: 既存プロセスルートの DO 連携
**対象ファイル**: `src/routes/process.ts`
- `import { registerProgressRoutes } from './progress';` を追加し、ルート登録関数を呼び出す
- `POST /api/process/:fileId` で Durable Object への状態更新をメイン経路にし、 KV への書き込みはフォールバック用に残す（DO 障害時のバックアップ）
- `PUT /api/process/:fileId/progress` （進捗更新エンドポイント）を新規追加し、 DO の `updateProgress` メソッドを呼び出す
- `GET /api/process/:fileId` で最初に DO から状態を取得し、失敗時のみ KV フォールバック

## ステップ2: クライアントサイド WebSocket 接続実装ガイドのドキュメント化
**ファイル**: `docs/client/progress-websocket.md` (新規)
- 接続手順、サンプルコード（JavaScript）、再接続ロジック（指数バックオフ）、エラーハンドリングを詳細に記載
- HTTP フォールバック（ポーリング）の実装例も掲載

## ステップ3: 後方互換性テストの作成・実行
**ファイル**: `src/routes/__tests__/progress-do-migration.test.ts` (新規)
- 既存KVベースの進捗更新がDO経由でも正常動作するかを検証
- DO障害時のKVフォールバック動作を確認（DO を意図的にエラーさせてテスト）
- 両方同時書き込みによる整合性テスト
- クライアント側WebSocket接続・メッセージ受信テスト（モック使用）

## ステップ4: モニタリング・メトリクス追加
**ファイル**: `src/lib/progress-metrics.ts` を Durable Object に組み込み
- `ProgressEngine` クラスにメトリクスプロパティ (`activeConnections`, `totalUpdates`, `broadcastBytes`) を追加
- `updateProgress` メソッド内でメトリクスをインクリメント
- `getMetrics()` メソッドでメトリクスを取得可能にする
- `/api/metrics/progress` エンドポイントを `routes/metrics.ts` に追加し、全 DO インスタンスのメトリクスを集約して返却（実装には全 DO インスタンスを列挙する仕組みが必要だが、簡易的にはサンプリングまたは別途 KV に集約）

## ステップ5: 設定・チューニングガイドのドキュメント化
**ファイル**: `docs/operational/progress-do.md` (新規)
- DOインスタンス数の見積もり式: `アクティブファイル数 × 1.2`（バッファ）
- メモリ使用量見積もり: 1インスタンスあたり数KB～十数KB
- スケーリング挙度: 自動（リクエストに応じてインスタンス生成）
- 故障対応: DOクラッシュ時は自動再起動、状態はストレージ（KV）より復元

## ステップ6: パフォーマンス比較ベンチマークの実施
**ファイル**: `benchmark/progress-do-vs-kv.ts` (新規)
- シナリオ: 100ファイル同時処理、各ファイルで10回進捗更新
- KVポーリング方式: クライアントが2秒間隔で10回 polling → 100ファイル × 10回 = 1,000 KV読み込み
- DO方式: 初期接続: 100 WebSocket接続（DO作成）、進捗更新: 100ファイル × 10回 = 1,000 DO更新（内部処理のみ、外部I/Oなし）、ブロードキャスト: 1,000メッセージ × 100クライアント = 100,000 メッセージ送信（ただしメモリ内）
- 結果期待値: KV読み込み書き込み 90%+ 削減、レイテンシ大幅改善
- ベンチマークスクリプトを実行し、結果をドキュメントに残す

## ステップ7: ドキュメント化・運用ガイド（続き）
**ファイル**: `docs/operational/progress-do.md` に追加
- 監視項目とアラート設定（例: WebSocket接続数急増、進捗更新停止等）
- トラブルシューティングガイド（DO が応答しない場合の対処法）

## ステップ8: テストカバレッジの向上
- 進捗関連のユニットテスト・統合テストを増やし、カバレッジを 80% 以上にする
- テストファイル: `src/lib/__tests__/progress-engine.test.ts`, `src/routes/__tests__/progress.test.ts`

## ステップ9: 完了条件確認
- [ ] WebSocketエンドポイント `/api/progress/:fileId` が実装済みかつ機能している
- [ ] HTTPフォールバックエンドポイント `/api/progress/:fileId/http` が実装済み
- [ ] 既存プロセスルートがDO経由で進捗更新（KVフォールバック付き）
- [ ] クライアントサイド実装ガイドがドキュメント化済み
- [ ] テストでDO連携・フォールバック・エラーケース網羅
- [ ] ベンチマークでKVアクセス削減効果確認（目標: 90%+ 削減）
- [ ] メトリクスエンドポイント `/api/metrics/progress` が実装され、有効なデータが返却される
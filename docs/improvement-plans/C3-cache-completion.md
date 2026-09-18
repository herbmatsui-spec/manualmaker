# C3: KV読み書きバッチ処理 & キャッシュの完成

## 概要
P3で実装された基盤（KVバッチユーティリティ、メモリキャッシュ、設定キャッシュ）を基に、国際化・PIIパターン・アップロード一覧・進捗一覧へのキャッシュ適用、キャッシュ無効化の連携、ベンチマーク・ドキュメント化を完了する。

---

## ステップ1: 国際化翻訳キャッシュの適用
**対象ファイル**: `src/routes/i18n.ts`
- `import { caches } from '../lib/memory-cache';`
- `/api/i18n/translations/:lang` エンドポイントで言語ごとにキャッシュを使用（キャッシュヒット時は即時返却、ミス時に `TRANSLATIONS[lang]` を取得後キャッシュ保存）

## ステップ2: PIIパターンキャッシュの適用
**対象ファイル**: `src/routes/security.ts`
- `import { caches } from '../lib/memory-cache';`
- `/api/security/patterns` エンドポイントで KV から取得した結果をメモリキャッシュに保存し、 subsequent リクエストではキャッシュから返却

## ステップ3: アップロード一覧取得最適化（N+1解決）
**対象ファイル**: `src/routes/upload.ts`
- `import { createKVBatch } from '../lib/kv-batch';`
- `app.get('/api/uploads', ...)` で `createKVBatch(c.env).getByPrefix<UploadedFile>('uploaded:')` を使用し、1 KV 操作で一覧取得を実現

## ステップ4: 進捗取得最適化（管理用エンドポイント追加）
**対象ファイル**: `src/routes/process.ts`
- `import { createKVBatch } from '../lib/kv-batch';`
- `app.get('/api/processes', ...)` を新規追加し、`createKVBatch(c.env).getByPrefix<ProcessingResult>('process:')` で進捗一覧を取得（管理用・デバッグ用）

## ステップ5: キャッシュ無効化戦略の連携
**ファイル**: `src/lib/cache-invalidation.ts`（既存）を適切な場面で呼び出す
- 設定変更API（将来実装時）では `invalidateConfig()` を呼び出す
- 翻訳変更APIでは `invalidateI18n(lang)` を呼び出す
- PIIパターン変更APIでは `invalidatePiiPatterns()` を呼び出す

## ステップ6: キャッシュの有効期限チューニング
**ファイル**: `src/lib/memory-cache.ts`
- 各キャッシュインスタンスの TTL を実運用に合わせて調整（例: 設定は 1時間、翻訳は 1時間、PIIパターンは 30分）
- 必要に応じて動的に TTL を変更できるメソッドを追加（将来の拡張性）

## ステップ7: 効果測定・ベンチマークの実施
**ファイル**: `benchmark/kv-cache-benchmark.ts` (新規)
- 改善前後での KV 読み込み回数比較シナリオを実装
- キャッシュヒット率測定、`/api/uploads` 100 リクエスト時の KV 操作数を計測
- メモリ使用量増加確認
- 結果をドキュメントに残す

## ステップ8: ドキュメント化
**ファイル**: `docs/operational/kv-cache.md` (新規)
- KV バッチ操作の使い方
- メモリキャッシュの適用シナリオとベストプラクティス
- キャッシュ無効化の手順

## ステップ9: 完了条件確認
- [ ] 全エンドポイントで KVBatch または メモリキャッシュが適用されている
- [ ] `/api/uploads` が 1 KV 操作で完了（list + バッチget）
- [ ] 設定/i18n/PIIパターンがメモリキャッシュヒットしている（ログまたはメトリクスで確認）
- [ ] テストでキャッシュ機能・無効化動作が確認できる
- [ ] ベンチマークで KV 読み込み回数削減効果が確認できる（目標: 90%+ 削減）
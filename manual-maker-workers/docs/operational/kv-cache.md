# KV キャッシュ運用ガイド

このドキュメントは、マニュアルメーカーシステムにおける KV バッチ操作とメモリキャッシュの使い方、ベストプラクティス、キャッシュ無劫化の手順について説明します。

## KV バッチ操作の使い方

KV バッチは、`src/lib/kv-batch.ts` で提供される `KVBatch` クラスを使用して、複数の KV 操作を効率的に行うためのラッパーです。

### 主なメソッド

- `getMany(keys: string[])`: 複数キーを並列取得
- `getByPrefix<T>(prefix: string, limit?: number)`: プレフィックス一致キーの一括取得（list + 並列get）
- `setMany(entries: { key: string; value: unknown; expirationTtl?: number }[])`: 複数キーを並列保存
- `deleteMany(keys: string[])`: 複数キーを並列削除

### 使用例

```typescript
import { createKVBatch } from '../lib/kv-batch';

// KVBatch インスタンス作成
const kvBatch = createKVBatch(c.env);

// プレフィックス一致で複数キーを取得（1 KV操作でリスト取得＋並列get）
const records = await kvBatch.getByPrefix<UploadedFile>('uploaded:');
const uploads = Object.values(records);

// 複数キーを並列保存
await kvBatch.setMany([
  { key: `uploaded:${id1}`, value: file1 },
  { key: `uploaded:${id2}`, value: file2 }
]);

// 複数キーを並列削除
await kvBatch.deleteMany([`uploaded:${id1}`, `uploaded:${id2}`]);
```

## メモリキャッシュの適用シナリオとベストプラクティス

メモリキャッシュは `src/lib/memory-cache.ts` で提供される `MemoryCache` クラスを使用し、グローバルインスタンス `caches` として利用可能です。

### 利用可能なキャッシュインスタンス

- `caches.config`: 設定データ（TTL: 1時間）
- `caches.i18n`: 国際化翻訳データ（TTL: 1時間）
- `caches.piiPatterns`: PII パターンデータ（TTL: 30分）

### 使用例

```typescript
import { caches } from '../lib/memory-cache';

// 設定取得（キャッシュあり）
const config = caches.config.get<ConfigResponse>('config');
if (!config) {
  // KV または環境変数から取得してキャッシュに保存
  const config = await loadConfigFromKV();
  caches.config.set('config', config);
}

// 翻訳取得（キャッシュあり）
const translations = caches.i18n.get<Record<string, string>>(lang);
if (!translations) {
  const translations = TRANSLATIONS[lang];
  if (!translations) {
    throw new NotFoundError(`Language: ${lang}`);
  }
  caches.i18n.set(lang, translations);
}

// PII パターン取得（キャッシュあり）
const piiData = caches.piiPatterns.get<{patterns: Array<...>, source: 'kv' | 'default'}>('piiPatterns');
if (!piiData) {
  const piiData = await loadPiiPatternsFromKV();
  caches.piiPatterns.set('piiPatterns', piiData);
}
```

### ベストプラクティス

1. **読み込みパスでキャッシュを使用**：データ取得の最初にキャッシュをチェックし、ミス時のみ元データソース（KV、ファイル等）から取得し、取得後にキャッシュに保存。
2. **TTLの調整**：データの更新頻度に応じてTTLを設定。頻繁に変更されないデータは長めのTTL、頻繁に変更されるデータは短めのTTL。
3. **キャッシュサイズの監視**：`caches.xxx.size()` メソッドで有効エントリ数を取得し、異常な増加がないか監視。
4. **例外安全性**：キャッシュ取得に失敗しても、元データソースからフォールバックできるように設計。

## キャッシュ無劫化の手順

キャッシュ無劫化は `src/lib/cache-invalidation.ts` で提供される関数を使用します。

### 利用可能な無劫化関数

- `invalidateConfig()`: 設定キャッシュを無劫化
- `invalidateI18n(lang?: string)`: 特定言語の翻訳キャッシュを無劫化（lang が未指定なら全言語クリア）
- `invalidatePiiPatterns()`: PII パターンキャッシュを無劫化

### 使用例

```typescript
import { invalidateConfig, invalidateI18n, invalidatePiiPatterns } from '../lib/cache-invalidation';

// 設定が変更されたとき
await updateConfigInKV();
invalidateConfig();

// 特定言語の翻訳が変更されたとき
await updateTranslationInKV(lang, newTranslations);
invalidateI18n(lang);

// PII パターンが変更されたとき
await updatePiiPatternsInKV(newPatterns);
invalidatePiiPatterns();
```

### 自動無劫化の組み込み

今後実装される設定変更API、翻訳変更API、PIIパターン変更API内で、上記の無劫化関数を呼び出すようにしてください。

## パフォーマンス考慮事項

- KV バッチ操作により、複数キーの取得・保存・削除が1回の KV 操作で完了し、レイテンシーとコストを大幅に削減。
- メモリキャッシュにより、同じデータの繰り返しアクセスが高速化され、KV 操作数を削減。
- キャッシュ無劫化により、古いデータが提供されることを防ぎ、データの整合性を保持。

## 関連ドキュメント

- [KV バッチ操作の詳細](../lib/kv-batch.ts)
- [メモリキャッシュの詳細](../lib/memory-cache.ts)
- [キャッシュ無劫化の詳細](../lib/cache-invalidation.ts)
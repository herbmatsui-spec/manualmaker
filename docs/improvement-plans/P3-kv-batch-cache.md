# P3: KV読み書きバッチ処理 & キャッシュ

## 概要
KVアクセスの効率化とキャッシュ導入により、無料枠消費削減とレスポンス高速化を実現する。N+1問題解決と頻繁アクセスデータのメモリキャッシュが中心。

---

## ステップ1: KVバッチ操作ユーティリティ作成
**ファイル**: `src/lib/kv-batch.ts` (新規)
```typescript
import type { Env } from '../lib/types';

export class KVBatch {
  constructor(private readonly kv: KVNamespace, private readonly env: Env) {}

  /**
   * 複数キーを並列取得
   * @param keys 取得したいキーの配列
   * @returns キーと値のマップ（存在しないキーは undefined）
   */
  async getMany<T = unknown>(keys: string[]): Promise<Record<string, T | undefined>> {
    const promises = keys.map(key => this.kv.get<T>(key, 'json'));
    const results = await Promise.all(promises);
    return Object.fromEntries(keys.map((key, i) => [key, results[i]]));
  }

  /**
   * プレフィックス一致キーの一括取得（list + 並列get）
   * @param prefix 検索プレフィックス
   * @param limit 最大取得件数（省略時は1000）
   * @returns キーと値のマップ
   */
  async getByPrefix<T = unknown>(prefix: string, limit?: number): Promise<Record<string, T>> {
    const list = await this.kv.list({ prefix, limit: limit ?? 1000 });
    if (!list.keys.length) return {};

    const promises = list.keys.map(key => this.kv.get<T>(key.name, 'json'));
    const results = await Promise.all(promises);
    return Object.fromEntries(
      list.keys.map((key, i) => [key.name, results[i]])
    ).filter(([, value]) => value !== undefined) as Record<string, T>;
  }

  /**
   * 複数キーを並列保存
   * @param entries キーと値のペア配列
   */
  async setMany(entries: { key: string; value: unknown; expirationTtl?: number }[]) {
    const promises = entries.map(({ key, value, expirationTtl }) =>
      this.kv.put(key, JSON.stringify(value), { expirationTtl })
    );
    await Promise.all(promises);
  }

  /**
   * 複数キーを並列削除
   * @param keys 削除したいキーの配列
   */
  async deleteMany(keys: string[]) {
    const promises = keys.map(key => this.kv.delete(key));
    await Promise.all(promises);
  }
}

/**
 * KVBatchインスタンス作成ヘルパー
 */
export function createKVBatch(env: Env) {
  return new KVBatch(env.PROCESSING_KV, env);
}
```

**確認**: `npx tsc --noEmit` で型エラーなし

---

## ステップ2: メモリキャッシュクラス実装
**ファイル**: `src/lib/memory-cache.ts` (新規)
```typescript
interface CacheEntry<T> {
  value: T;
  expiresAt: number; // timestamp in ms
}

export class MemoryCache<T> {
  private store = new Map<string, CacheEntry<T>>();
  private readonly defaultTtl: number;

  constructor(defaultTtlSeconds = 300) {
    this.defaultTtl = defaultTtlSeconds * 1000;
  }

  /**
   * 値を取得（存在しないか期限切れなら undefined）
   */
  get(key: string): T | undefined {
    const entry = this.store.get(key);
    if (!entry) return undefined;

    if (Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return undefined;
    }

    return entry.value;
  }

  /**
   * 値を保存
   * @param ttlSeconds 生存時間（秒）、省略時はデフォルトTTL
   */
  set(key: string, value: T, ttlSeconds?: number) {
    const ttl = ttlSeconds ?? this.defaultTtl / 1000;
    const expiresAt = Date.now() + ttl * 1000;
    this.store.set(key, { value, expiresAt });
  }

  /**
   * キーを削除
   */
  delete(key: string): boolean {
    return this.store.delete(key);
  }

  /**
   * 全てクリア
   */
  clear() {
    this.store.clear();
  }

  /**
   * 有効エントリ数取得
   */
  size(): number {
    this.cleanupExpired();
    return this.store.size;
  }

  private cleanupExpired() {
    const now = Date.now();
    for (const [key, entry] of this.store.entries()) {
      if (now > entry.expiresAt) {
        this.store.delete(key);
      }
    }
  }
}

/**
 * グローバルキャッシュインスタンス（ワーカー単体なのでプロセス内共有可）
 */
export const caches = {
  config: new MemoryCache(3600), // 1時間
  i18n: new MemoryCache(3600), // 1時間
  piiPatterns: new MemoryCache(1800), // 30分
};
```

---

## ステップ3: 設定取得最適化
**対象ファイル**: `src/routes/config.ts`
- 現在: 全リクエストで `c.env` から値取得（軽微だが毎回）
- 最適化: 起動時に1回読み込み、メモリキャッシュに保存

```typescript
// src/lib/config-cache.ts (新規)
import type { Env } from '../lib/types';
import { caches } from './memory-cache';

export function getConfig(env: Env) {
  const cached = caches.config.get<ConfigResponse>('config');
  if (cached) return cached;

  const config: ConfigResponse = {
    geminiModelName: env.GEMINI_MODEL_NAME || 'gemini-1.5-flash',
    processorType: 'cloudflare-workers',
    pdfDpi: 300,
    maxFileSizeMb: parseInt(env.MAX_FILE_SIZE_MB || '50', 10),
    webUploadMaxMb: parseInt(env.WEB_UPLOAD_MAX_MB || '100', 10),
    outputDirectory: 'r2://manual-processor-files',
    supportedExtensions: ['.pdf'],
    defaultLanguage: env.DEFAULT_LANGUAGE || 'ja',
  };

  caches.config.set('config', config);
  return config;
}

// routes/config.ts 修正
import { getConfig } from '../lib/config-cache';

export function registerConfigRoutes(app: Hono<{ Bindings: Env }>) {
  app.get('/api/config', (c) => {
    const config = getConfig(c.env);
    return c.json(config);
  });
}
```

**確認**: キャッシュヒットで `c.env` アクセス削減、起動後は変化なし（変数は不変前提）

---

## ステップ4: 国際化翻訳キャッシュ
**対象ファイル**: `src/routes/i18n.ts`
- 現在: 全リクエストで `TRANSLATIONS` オブジェクト参照（メモリ内なので軽微だが統一のためキャッシュ化）
- 最適化: 言語ごとにキャッシュ

```typescript
// i18n.ts 修正
import { caches } from '../lib/memory-cache';

export function registerI18nRoutes(app: Hono<{ Bindings: Env }>) {
  app.get('/api/i18n/languages', (c) => {
    return c.json({ languages: Object.keys(TRANSLATIONS), default: 'ja' });
  });

  app.get('/api/i18n/translations/:lang', (c) => {
    const lang = c.req.param('lang');
    const cached = caches.i18n.get<Record<string, string>>(`i18n:${lang}`);
    if (cached) {
      return c.json({ lang, translations: cached });
    }

    const translations = TRANSLATIONS[lang];
    if (!translations) {
      return c.json({ error: `Unsupported language: ${lang}` }, 404);
    }

    caches.i18n.set(`i18n:${lang}`, translations);
    return c.json({ lang, translations });
  });

  // detect は軽量なのでキャッシュ不要（頻度低く、文字列長依存）
}
```

---

## ステップ5: PIIパターンキャッシュ
**対象ファイル**: `src/routes/security.ts`
- 現在: KV読み込みかハードコート値返却
- 最適化: KV読み込み結果をキャッシュ

```typescript
// security.ts 修正
import { caches } from '../lib/memory-cache';
import { createKVBatch } from '../lib/kv-batch';

app.get('/api/security/patterns', async (c) => {
  try {
    const cached = caches.piiPatterns.get<Array<{pattern: string; label: string; replacement: string}>>('piiPatterns');
    if (cached) {
      return c.json({ patterns: cached, source: 'cache' });
    }

    // KVから取得（失敗時はデフォルト）
    let patterns: typeof DEFAULT_PII_PATTERNS | null = null;
    if (c.env.PROCESSING_KV) {
      const custom = await c.env.PROCESSING_KV.get('pii_patterns', 'json');
      if (custom && Array.isArray((custom as any).patterns)) {
        patterns = (custom as any).patterns;
      }
    }

    if (patterns) {
      caches.piiPatterns.set('piiPatterns', patterns);
      return c.json({ patterns, source: 'kv' });
    }

    caches.piiPatterns.set('piiPatterns', DEFAULT_PII_PATTERNS);
    return c.json({ patterns: DEFAULT_PII_PATTERNS, source: 'default' });
  } catch (error) {
    console.error('Get patterns error:', error);
    return c.json({ patterns: DEFAULT_PII_PATTERNS, source: 'default' });
  }
});
```

---

## ステップ6: アップロード一覧取得最適化（N+1解決）
**対象ファイル**: `src/routes/upload.ts`
- 現在: `list()` + 個別 `get()` のN+1
- 最適化: KVBatch の `getByPrefix` 使用

```typescript
// upload.ts 修正
import { createKVBatch } from '../lib/kv-batch';

app.get('/api/uploads', async (c) => {
  try {
    const kvBatch = createKVBatch(c.env);
    const uploads = await kvBatch.getByPrefix<UploadedFile>('uploaded:');
    
    const uploadsArray: UploadedFile[] = Object.values(uploads);
    return c.json({ uploads: uploadsArray });
  } catch (error) {
    console.error('List uploads error:', error);
    return c.json({ error: 'Failed to list uploads' }, 500);
  }
});
```

---

## ステップ7: 進捗取得最適化（プロセス状態取得）
**対象ファイル**: `src/routes/process.ts`
- 現在: 個別 `get()`
- 最適化: 現状は個別取得が適切（キー特定済み）だが、複数ファイル一覧取得時にバッチ適用

```typescript
// progress一覧取得エンドポイント追加（管理用）
app.get('/api/processes', async (c) => {
  try {
    const kvBatch = createKVBatch(c.env);
    const processes = await kvBatch.getByPrefix<ProcessingResult>('process:');
    
    const processesArray: ProcessingResult[] = Object.values(processes);
    return c.json({ processes: processesArray });
  } catch (error) {
    console.error('List processes error:', error);
    return c.json({ error: 'Failed to list processes' }, 500);
  }
});
```

---

## ステップ8: キャッシュ無効化戦略
**ファイル**: `src/lib/cache-invalidation.ts` (新規)
- 現在実装では不変データ前提（設定、翻訳、パターンは変更頻度低）
- 変更が必要な場合のための無関数

```typescript
export function invalidateConfig() {
  caches.config.delete('config');
}

export function invalidateI18n(lang?: string) {
  if (lang) {
    caches.i18n.delete(`i18n:${lang}`);
  } else {
    // 全言語クリア（非効率だが頻度低い操作想定）
    caches.i18n.clear();
  }
}

export function invalidatePiiPatterns() {
  caches.piiPatterns.delete('piiPatterns');
}
```

**使用例**: 設定変更API実装時に呼び出し（現状は変更不可前提のため保留）

---

## ステップ9: 効果測定・ベンチマーク
**ファイル**: `benchmark/kv-cache-benchmark.ts` (新規)
- 改善前後での KV読み込み回数比較
- キャッシュヒット率測定
- メモリ使用量増加確認

```typescript
// シナリオ: /api/uploads 呼び出し 100回
// 改善前: list() + N個の get() = 1 + N KV操作
// 改善後: getByPrefix() = 1 KV操作（内部で並列だが1バッチ）

// 結果期待値: 90%+ KV操作削減
```

---

## 完了条件
- [ ] 全エンドポイントで KVBatch または メモリキャッシュ適用
- [ ] `/api/uploads` が 1 KV操作で完了（list + バッチget）
- [ ] 設定/i18n/PIIパターンがメモリキャッシュヒット
- [ ] テストでキャッシュ機能・無効化動作確認
- [ ] ベンチマークで KV読み込み回数削減確認
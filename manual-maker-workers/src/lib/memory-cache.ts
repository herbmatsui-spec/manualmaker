import type { ConfigResponse } from './types';

interface CacheEntry<T> {
  value: T;
  expiresAt: number; // timestamp in ms
}

export class MemoryCache<T> {
  private store = new Map<string, CacheEntry<T>>();
  private defaultTtl: number;

  constructor(defaultTtlSeconds = 300) {
    this.defaultTtl = defaultTtlSeconds * 1000;
  }

  /**
   * 値を取得（存在しないか期限切れなら undefined）
   */
  get<U = T>(key: string): U | undefined {
    const entry = this.store.get(key);
    if (!entry) return undefined;

    if (Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return undefined;
    }

    return entry.value as unknown as U;
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

    /**
     * デフォルトTTLを変更（新規エントリに適用）
     * @param ttlSeconds 新しいデフォルトTTL（秒）
     */
    setDefaultTtl(ttlSeconds: number) {
      this.defaultTtl = ttlSeconds * 1000;
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
  config: new MemoryCache<ConfigResponse>(3600),
  i18n: new MemoryCache<Record<string, string>>(3600),
  piiPatterns: new MemoryCache<{patterns: Array<{pattern: string; label: string; replacement: string}>; source: 'kv' | 'default' }>(1800),
};
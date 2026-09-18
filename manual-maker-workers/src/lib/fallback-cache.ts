import type { Env } from './types';

export class FallbackCache {
  constructor(
    private readonly kv: KVNamespace,
    private readonly defaultTtlSeconds: number = 300 // 5 minutes default
  ) {}

  async cacheResult<T>(key: string, value: T, ttlSeconds?: number): Promise<void> {
    const ttl = ttlSeconds ?? this.defaultTtlSeconds;
    await this.kv.put(
      `fallback:${key}`, 
      JSON.stringify(value), 
      { expirationTtl: ttl }
    );
  }

  async getCachedResult<T>(key: string): Promise<T | null> {
    const cached = await this.kv.get(`fallback:${key}`, 'text');
    if (cached === null) return null;
    
    try {
      return JSON.parse(cached) as T;
    } catch (e) {
      console.error(`Failed to parse cached value for key ${key}:`, e);
      return null;
    }
  }

  async invalidate(key: string): Promise<void> {
    await this.kv.delete(`fallback:${key}`);
  }

  async invalidateByPrefix(prefix: string): Promise<void> {
    let cursor: string | undefined;
    do {
      const list: KVNamespaceListResult<unknown> = await this.kv.list({
        prefix: `fallback:${prefix}`,
        cursor,
      });
      // Workers KV has no bulk delete API; bound concurrent requests per batch.
      for (let i = 0; i < list.keys.length; i += 20) {
        await Promise.all(list.keys.slice(i, i + 20).map(key => this.kv.delete(key.name)));
      }
      cursor = list.list_complete ? undefined : list.cursor;
    } while (cursor);
  }
}

export function createFallbackCache(env: Env) {
  return new FallbackCache(env.PROCESSING_KV);
}
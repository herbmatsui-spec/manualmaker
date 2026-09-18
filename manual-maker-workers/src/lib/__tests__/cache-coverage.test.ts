import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryCache } from '../memory-cache';
import { createFallbackCache } from '../fallback-cache';
import { createKVBatch } from '../kv-batch';
import type { Env } from '../types';

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-09-17T00:00:00Z'));
});
afterEach(() => vi.useRealTimers());

function storage() {
  const get = vi.fn();
  const put = vi.fn().mockResolvedValue(undefined);
  const remove = vi.fn().mockResolvedValue(undefined);
  const list = vi.fn();
  const env = { PROCESSING_KV: { get, put, delete: remove, list } } as unknown as Env;
  return { env, get, put, remove, list };
}

describe('MemoryCache', () => {
  it('expires values and removes stale entries during size calculation', () => {
    const cache = new MemoryCache<string>(2);
    expect(cache.get('missing')).toBeUndefined();
    cache.set('short', 'one');
    cache.set('long', 'two', 10);
    expect(cache.get('short')).toBe('one');
    expect(cache.size()).toBe(2);
    vi.advanceTimersByTime(2001);
    expect(cache.get('short')).toBeUndefined();
    expect(cache.size()).toBe(1);
    vi.advanceTimersByTime(8000);
    expect(cache.size()).toBe(0);
  });

  it('applies changed defaults only to new entries and supports deletion/clear', () => {
    const cache = new MemoryCache<number>();
    cache.set('old', 1);
    cache.setDefaultTtl(1);
    cache.set('new', 2);
    vi.advanceTimersByTime(1001);
    expect(cache.get('new')).toBeUndefined();
    expect(cache.get('old')).toBe(1);
    expect(cache.delete('old')).toBe(true);
    expect(cache.delete('old')).toBe(false);
    cache.set('remaining', 3);
    cache.clear();
    expect(cache.size()).toBe(0);
  });
});

describe('FallbackCache', () => {
  it('serializes values with default and explicit TTLs', async () => {
    const { env, get, put, remove } = storage();
    const cache = createFallbackCache(env);
    await cache.cacheResult('first', { a: 1 });
    await cache.cacheResult('second', false, 600);
    expect(put.mock.calls).toEqual([
      ['fallback:first', '{"a":1}', { expirationTtl: 300 }],
      ['fallback:second', 'false', { expirationTtl: 600 }],
    ]);
    get.mockResolvedValueOnce('{"a":1}').mockResolvedValueOnce(null).mockResolvedValueOnce('invalid');
    expect(await cache.getCachedResult('first')).toEqual({ a: 1 });
    expect(await cache.getCachedResult('missing')).toBeNull();
    expect(await cache.getCachedResult('corrupt')).toBeNull();
    expect(get).toHaveBeenCalledWith('fallback:first', 'text');
    await cache.invalidate('first');
    expect(remove).toHaveBeenCalledWith('fallback:first');
  });

  it('invalidates all pages of matching keys', async () => {
    const { env, list, remove } = storage();
    const names = Array.from({ length: 25 }, (_, i) => `fallback:group:${i}`);
    list.mockResolvedValueOnce({ keys: names.map(name => ({ name })), list_complete: false, cursor: 'next' })
      .mockResolvedValueOnce({ keys: [{ name: 'fallback:group:last' }], list_complete: true });
    await createFallbackCache(env).invalidateByPrefix('group:');
    expect(list.mock.calls).toEqual([
      [{ prefix: 'fallback:group:', cursor: undefined }],
      [{ prefix: 'fallback:group:', cursor: 'next' }],
    ]);
    expect(remove.mock.calls.flat()).toEqual([...names, 'fallback:group:last']);
  });

  it('propagates storage read and write errors', async () => {
    const { env, get, put } = storage();
    const cache = createFallbackCache(env);
    get.mockRejectedValue(new Error('read failed'));
    put.mockRejectedValue(new Error('write failed'));
    await expect(cache.getCachedResult('key')).rejects.toThrow('read failed');
    await expect(cache.cacheResult('key', 1)).rejects.toThrow('write failed');
  });
});

describe('KVBatch', () => {
  it('preserves requested keys and maps absent values to undefined', async () => {
    const { env, get } = storage();
    get.mockResolvedValueOnce({ a: 1 }).mockResolvedValueOnce(null);
    const batch = createKVBatch(env);
    expect(await batch.getMany(['one', 'missing'])).toEqual({ one: { a: 1 }, missing: undefined });
    expect(get.mock.calls).toEqual([['one', 'json'], ['missing', 'json']]);
    expect(await batch.getMany([])).toEqual({});
  });

  it('lists with limits and omits keys removed between list and get', async () => {
    const { env, get, list } = storage();
    list.mockResolvedValueOnce({ keys: [] }).mockResolvedValueOnce({ keys: [{ name: 'one' }, { name: 'gone' }] });
    get.mockResolvedValueOnce(0).mockResolvedValueOnce(null);
    const batch = createKVBatch(env);
    expect(await batch.getByPrefix('empty')).toEqual({});
    expect(await batch.getByPrefix('prefix', 20)).toEqual({ one: 0 });
    expect(list.mock.calls).toEqual([[{ prefix: 'empty', limit: 1000 }], [{ prefix: 'prefix', limit: 20 }]]);
  });

  it('writes JSON entries and deletes supplied keys', async () => {
    const { env, put, remove } = storage();
    const batch = createKVBatch(env);
    await batch.setMany([{ key: 'one', value: { a: 1 }, expirationTtl: 60 }, { key: 'two', value: false }]);
    expect(put.mock.calls).toEqual([['one', '{"a":1}', { expirationTtl: 60 }], ['two', 'false', { expirationTtl: undefined }]]);
    await batch.deleteMany(['one', 'two']);
    expect(remove.mock.calls).toEqual([['one'], ['two']]);
    put.mockRejectedValue(new Error('unavailable'));
    await expect(batch.setMany([{ key: 'one', value: 1 }])).rejects.toThrow('unavailable');
  });
});

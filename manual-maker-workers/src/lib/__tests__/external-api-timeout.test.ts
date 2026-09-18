import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createGeminiApi, createVisionApi } from '../external-api';
import type { Env } from '../types';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals(); });

const operations = [
  { name: 'content', timeout: 10_000, run: (env: Env) => {
    const api = createGeminiApi(env);
    return { api, pending: api.generateContent({ contents: [{ parts: [{ text: 'test' }] }] }) };
  } },
  { name: 'models', timeout: 10_000, run: (env: Env) => {
    const api = createGeminiApi(env);
    return { api, pending: api.listModels() };
  } },
  { name: 'vision', timeout: 15_000, run: (env: Env) => {
    const api = createVisionApi(env);
    return { api, pending: api.annotateImage({ requests: [{ image: { content: 'dGVzdA==' }, features: [{ type: 'TEXT_DETECTION' }] }] }) };
  } },
];

describe('C04 wrapper timeout cancellation (mock fetch, real retry helper)', () => {
  it.each(operations)('aborts $name without retrying or caching', async operation => {
    let signal: AbortSignal | null | undefined;
    let started!: () => void;
    const ready = new Promise<void>(resolve => { started = resolve; });
    const fetch = vi.fn((_url: string, options: RequestInit) => {
      signal = options.signal;
      started();
      return new Promise<Response>((_resolve, reject) => {
        signal?.addEventListener('abort', () => reject(signal?.reason), { once: true });
      });
    });
    vi.stubGlobal('fetch', fetch);
    const put = vi.fn();
    const env = { GEMINI_API_KEY: 'test-key', GOOGLE_API_KEY: 'test-key',
      PROCESSING_KV: { put, get: vi.fn().mockResolvedValue(null) } } as unknown as Env;
    const { api, pending } = operation.run(env);
    const observed = pending.catch(error => error);
    await ready;
    await vi.advanceTimersByTimeAsync(operation.timeout);
    expect(await observed).toMatchObject({ message: `Operation timeout after ${operation.timeout}ms` });
    expect(signal?.aborted).toBe(true);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(put).not.toHaveBeenCalled();
    expect(api.getCircuitMetrics().failureCount).toBe(1);
    expect(vi.getTimerCount()).toBe(0);
  });
});

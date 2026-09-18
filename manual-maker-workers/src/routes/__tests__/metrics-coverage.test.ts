import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Hono } from 'hono';
import { registerMetricsRoutes, setApiInstances } from '../metrics';
import { createGeminiApi, createVisionApi } from '../../lib/external-api';
import { rateLimitConfigs } from '../../lib/rate-limiter';
import type { AppEnv, Env } from '../../lib/types';

let app: Hono<AppEnv>;
let env: Env;
let list: ReturnType<typeof vi.fn>;
let get: ReturnType<typeof vi.fn>;

beforeEach(() => {
  list = vi.fn().mockResolvedValue({ keys: [], list_complete: true });
  get = vi.fn().mockResolvedValue(null);
  env = { PROCESSING_KV: { list, get } } as unknown as Env;
  app = new Hono<AppEnv>();
  registerMetricsRoutes(app);
});

describe('metrics routes', () => {
  it('reports and resets registered circuit breakers', async () => {
    const gemini = createGeminiApi(env);
    const vision = createVisionApi(env);
    const geminiReset = vi.spyOn(gemini, 'resetCircuitBreaker');
    const visionReset = vi.spyOn(vision, 'resetCircuitBreaker');
    setApiInstances(gemini, vision);
    const response = await app.request('/api/metrics/circuit-breakers', {}, env);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      gemini: { name: 'gemini-api', state: 'closed', failureCount: 0 },
      vision: { name: 'vision-api', state: 'closed', failureCount: 0 },
      timestamp: expect.any(String),
    });
    const reset = await app.request('/api/system/reset-circuit-breakers', { method: 'POST' }, env);
    expect(await reset.json()).toMatchObject({ success: true, message: 'Circuit breakers reset' });
    expect(geminiReset).toHaveBeenCalledOnce();
    expect(visionReset).toHaveBeenCalledOnce();
  });

  it('reports zero activity for empty rate limit windows', async () => {
    const response = await app.request('/api/metrics/rate-limit', {}, env);
    expect(response.status).toBe(200);
    const body = await response.json() as { rateLimitMetrics: Record<string, unknown> };
    for (const [name, config] of Object.entries(rateLimitConfigs)) {
      expect(body.rateLimitMetrics[name]).toMatchObject({ windowMs: config.windowMs, maxRequests: config.maxRequests, totalRequests: 0, blockedRequests: 0, uniqueIdentifiers: 0 });
      expect(list).toHaveBeenCalledWith({ prefix: `${config.keyPrefix}:` });
    }
  });

  it('ignores malformed and unrelated rate limit records', async () => {
    list.mockResolvedValue({ keys: [{ name: 'invalid' }, { name: 'unrelated:id:0' }], list_complete: true });
    const response = await app.request('/api/metrics/rate-limit', {}, env);
    expect(response.status).toBe(200);
    expect(get).not.toHaveBeenCalled();
  });

  it('aggregates every page of progress records and handles missing fields', async () => {
    list.mockResolvedValueOnce({ keys: [{ name: 'first' }, { name: 'gone' }], list_complete: false, cursor: 'next' })
      .mockResolvedValueOnce({ keys: [{ name: 'second' }, { name: 'empty' }], list_complete: true });
    get.mockResolvedValueOnce({ activeConnections: 2, totalUpdates: 3, broadcastBytes: 10 })
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({ activeConnections: 4, totalUpdates: 5, broadcastBytes: 20 })
      .mockResolvedValueOnce({});
    const response = await app.request('/api/metrics/progress', {}, env);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ timestamp: expect.any(String), activeConnections: 6, totalUpdates: 8, broadcastBytes: 30, sources: 3 });
    expect(list).toHaveBeenLastCalledWith({ prefix: 'progress-metrics:', cursor: 'next', limit: 1000 });
    expect(get).toHaveBeenCalledWith('first', 'json');
  });

  it.each([
    ['/api/metrics/progress', 'Failed to get progress metrics'],
    ['/api/metrics/rate-limit', 'Failed to get rate limit metrics'],
  ])('returns an error if storage fails at %s', async (path, error) => {
    list.mockRejectedValue(new Error('storage unavailable'));
    const response = await app.request(path, {}, env);
    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({ error });
  });
});

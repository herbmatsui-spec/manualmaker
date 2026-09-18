import { afterEach, describe, expect, it, vi } from 'vitest';
import { Hono } from 'hono';
import { OpenAPIHono } from '@hono/zod-openapi';
import { registerI18nRoutes } from '../../routes/i18n';
import { registerMermaidRoutes } from '../../routes/mermaid';
import { registerSecurityRoutes } from '../../routes/security';
import { registerMetricsRoutes } from '../../routes/metrics';
import { MemoryCache, caches } from '../memory-cache';
import { FailoverManager } from '../failover-manager';
import { openapiFileIdParam, openapiUploadBody } from '../openapi-schemas';
import type { AppEnv, Env } from '../types';

vi.mock('cloudflare:workers', () => ({
  DurableObject: class {
    constructor(protected ctx: DurableObjectState, protected env: Env) {}
  }
}));

const fileId = '550e8400-e29b-41d4-a716-446655440000';
const jsonRequest = (body: unknown) => ({
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
});
const makeEnv = () => ({
  RATE_LIMIT_ENABLED: 'false',
  PROCESSING_KV: { get: vi.fn().mockResolvedValue(null), put: vi.fn().mockResolvedValue(undefined) },
  BUCKET: { get: vi.fn(), put: vi.fn().mockResolvedValue({}) }
}) as unknown as Env;

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  caches.i18n.clear();
  caches.piiPatterns.clear();
});

describe('production registration regressions', () => {
  it('serves language routes and generates parameterized OpenAPI paths', async () => {
    const app = new OpenAPIHono<AppEnv>();
    registerI18nRoutes(app);
    const env = makeEnv();
    const response = await app.request('/api/i18n/languages', {}, env);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ languages: ['ja', 'en'], default: 'ja' });
    const translations = await app.request('/api/i18n/translations/en', {}, env);
    expect(translations.status).toBe(200);
    expect(await translations.json()).toMatchObject({ lang: 'en', translations: { upload_button: 'Upload' } });
    const detected = await app.request('/api/i18n/detect', jsonRequest({ text: 'こんにちは' }), env);
    expect(await detected.json()).toMatchObject({ detected: 'ja' });
    const doc = app.getOpenAPIDocument({ openapi: '3.0.0', info: { title: 'Test', version: '1' } });
    expect(doc.paths?.['/api/i18n/translations/{lang}']?.get).toBeDefined();
  });

  it('saves Mermaid source through validated path and body parameters', async () => {
    const app = new OpenAPIHono<AppEnv>();
    registerMermaidRoutes(app);
    const env = makeEnv();
    const response = await app.request(`/api/mermaid/save/${fileId}`, jsonRequest({ mermaid: 'graph TD; A-->B' }), env);
    expect(response.status).toBe(200);
    expect(env.BUCKET.put).toHaveBeenCalledWith(`results/${fileId}/diagram.mmd`, 'graph TD; A-->B', expect.any(Object));
    const doc = app.getOpenAPIDocument({ openapi: '3.0.0', info: { title: 'Test', version: '1' } });
    expect(doc.paths?.['/api/mermaid/save/{fileId}']?.post).toBeDefined();
  });

  it('masks valid text and returns 413 rather than 400 for oversized text', async () => {
    const app = new OpenAPIHono<AppEnv>();
    registerSecurityRoutes(app);
    const env = makeEnv();
    const response = await app.request('/api/security/mask', jsonRequest({ text: 'Contact alice@example.com' }), env);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ maskedText: 'Contact xxx@example.com', counts: { email: 1 } });
    const oversized = await app.request('/api/security/mask', jsonRequest({ text: 'x'.repeat(1024 * 1024 + 1) }), env);
    expect(oversized.status).toBe(413);
    expect(await oversized.json()).toMatchObject({ error: { code: 'VALIDATION_ERROR' } });
    const invalid = await app.request('/api/security/mask', jsonRequest({ text: 1 }), env);
    expect(invalid.status).toBe(400);
  });

  it('imports the production entrypoint with registered OpenAPI routes', async () => {
    const { app } = await import('../../index');
    const response = await app.request('/api/i18n/languages', {}, makeEnv());
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ languages: ['ja', 'en'] });
  });

  it('retains valid OpenAPI object examples and upload validation', () => {
    expect(openapiFileIdParam.parse({ fileId })).toEqual({ fileId });
    expect(openapiUploadBody.safeParse({}).success).toBe(false);
    expect(openapiUploadBody.safeParse({ file: new File(['pdf'], 'manual.pdf', { type: 'application/pdf' }) }).success).toBe(true);
  });
});

describe('production storage and progress regressions', () => {
  it('applies mutable default TTL only to new cache entries', () => {
    vi.useFakeTimers();
    const cache = new MemoryCache<string>(60);
    cache.set('old', 'old');
    cache.setDefaultTtl(1);
    cache.set('new', 'new');
    vi.advanceTimersByTime(1001);
    expect(cache.get('new')).toBeUndefined();
    expect(cache.get('old')).toBe('old');
    expect(cache.size()).toBe(1);
  });

  it('reports primary failure independently of a healthy secondary', async () => {
    const env = makeEnv();
    env.BUCKET = { list: vi.fn().mockRejectedValue(new Error('offline')) } as unknown as R2Bucket;
    env.BUCKET_SECONDARY = { list: vi.fn().mockResolvedValue({ objects: [] }) } as unknown as R2Bucket;
    const manager = new FailoverManager(env);
    expect(await manager.checkR2Health()).toEqual({ primary: false, secondary: true });
    expect(manager.getStatus()).toMatchObject({ primaryR2Healthy: false, secondaryR2Healthy: true });
  });

  it('aggregates KV metric pages using names and list_complete', async () => {
    const env = makeEnv();
    const list = vi.fn()
      .mockResolvedValueOnce({ keys: [{ name: 'progress-metrics:a' }], list_complete: false, cursor: 'next' })
      .mockResolvedValueOnce({ keys: [{ name: 'progress-metrics:b' }], list_complete: true });
    env.PROCESSING_KV = {
      list,
      get: vi.fn().mockResolvedValue({ activeConnections: 1, totalUpdates: 2, broadcastBytes: 3 })
    } as unknown as KVNamespace;
    const app = new Hono<AppEnv>();
    registerMetricsRoutes(app);
    const response = await app.request('/api/metrics/progress', {}, env);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ activeConnections: 2, totalUpdates: 4, broadcastBytes: 6, sources: 2 });
    expect(list).toHaveBeenCalledTimes(2);
    expect(list).toHaveBeenLastCalledWith({ prefix: 'progress-metrics:', cursor: 'next', limit: 1000 });
    expect(env.PROCESSING_KV.get).toHaveBeenCalledWith('progress-metrics:a', 'json');
  });

  it('restores Durable Object state and persists updates with the inherited environment', async () => {
    const { ProgressEngine } = await import('../progress-engine');
    const state = { fileId, status: 'processing' as const, progress: 1, stage: 'start' };
    let initialized: Promise<unknown> | undefined;
    const ctx = {
      id: { toString: () => 'durable-id' },
      storage: { get: vi.fn().mockResolvedValue(state), put: vi.fn(), delete: vi.fn() },
      blockConcurrencyWhile: (callback: () => Promise<unknown>) => { initialized = callback(); },
      waitUntil: vi.fn()
    } as unknown as DurableObjectState;
    const env = makeEnv();
    const engine = new ProgressEngine(ctx, env);
    await initialized;
    expect(await engine.queryProgress()).toEqual(state);
    await engine.updateProgress({ ...state, progress: 50 });
    expect(ctx.storage.put).toHaveBeenCalledWith('state', expect.objectContaining({ progress: 50, updatedAt: expect.any(String) }));
    expect(env.PROCESSING_KV.put).toHaveBeenCalledWith('progress-metrics:durable-id', expect.any(String), { expirationTtl: 3600 });
    expect((await engine.fetch(new Request('https://example.test'))).status).toBe(426);
    await engine.clear();
    expect(await engine.queryProgress()).toBeNull();
  });
});

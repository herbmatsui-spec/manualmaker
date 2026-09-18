import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApp } from '../../app';
import { appErrorResponseSchema } from '../openapi';
import type { Env } from '../../lib/types';

const env = { RATE_LIMIT_ENABLED: 'false', GEMINI_API_KEY: 'test-only-key' } as Env;
const path = '/api/gemini/gemini-1.5-flash/generateContent';
const request = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' };

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); });

describe('P9 Gemini contracts with real retry wrapper', () => {
  it.each([
    ['generateContent', { candidates: [{ content: { parts: [{ text: 'Manual' }] } }] }],
    ['countTokens', { totalTokens: 12 }],
    ['streamGenerateContent', [{ candidates: [] }]],
  ])('preserves upstream JSON for %s', async (method, payload) => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(payload));
    vi.stubGlobal('fetch', fetchMock);
    const app = createApp();
    const response = await app.request(`/api/gemini/gemini-1.5-flash/${method}`, request, env);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(payload);
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:${method}`,
      expect.objectContaining({ method: 'POST', body: '{}', headers: {
        'Content-Type': 'application/json', 'x-goog-api-key': 'test-only-key',
      } }),
    );
  });

  it('publishes both operations and returns the upstream model list', async () => {
    const payload = { models: [{ name: 'models/example' }], nextPageToken: 'next' };
    const fetchMock = vi.fn().mockResolvedValue(Response.json(payload));
    vi.stubGlobal('fetch', fetchMock);
    const app = createApp();
    const specResponse = await app.request('/api/doc', undefined, env);
    expect(specResponse.status).toBe(200);
    const spec = await specResponse.json() as { paths: Record<string, Record<string, {
      responses: Record<string, unknown>; parameters?: unknown[];
    }>> };
    expect(spec.paths['/api/gemini/{model}/{method}'].post.parameters).toEqual(expect.arrayContaining([
      expect.objectContaining({ name: 'model', in: 'path', required: true }),
      expect.objectContaining({ name: 'method', in: 'path', required: true }),
    ]));
    expect(spec.paths['/api/gemini/models'].get.responses['200']).toMatchObject({ content: { 'application/json': {} } });
    expect(spec.paths['/api/gemini/{model}/{method}'].post.responses['502']).toMatchObject({
      content: { 'application/json': { schema: { required: ['error'] } } },
    });
    const response = await app.request('/api/gemini/models', undefined, env);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(payload);
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith('https://generativelanguage.googleapis.com/v1beta/models', {
      headers: { 'x-goog-api-key': 'test-only-key' },
    });
  });

  it.each([path, '/api/gemini/models'])('returns 502 without network access for missing credentials: %s', async url => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock);
    const response = await createApp().request(url, url === path ? request : undefined,
      { RATE_LIMIT_ENABLED: 'false' } as Env);
    expect(response.status).toBe(502);
    expect(appErrorResponseSchema.parse(await response.json()).error.code).toBe('EXTERNAL_API_ERROR');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('maps non-retryable upstream errors to 502', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const fetchMock = vi.fn().mockResolvedValue(new Response('Forbidden', { status: 403 }));
    vi.stubGlobal('fetch', fetchMock);
    const response = await createApp().request(path, request, env);
    expect(response.status).toBe(502);
    expect(appErrorResponseSchema.parse(await response.json()).error.code).toBe('EXTERNAL_API_ERROR');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('sanitizes retry exhaustion as a 500 under the current retry policy', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockImplementation(async () => new Response('Unavailable', { status: 503 }));
    vi.stubGlobal('fetch', fetchMock);
    const pending = createApp().request(path, request, env);
    await vi.runAllTimersAsync();
    const response = await pending;
    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({ error: { code: 'INTERNAL_ERROR', message: 'Internal server error',
      requestId: response.headers.get('x-request-id') } });
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it('rejects an unsupported method before network access', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock);
    const response = await createApp().request('/api/gemini/example/unsupported', request, env);
    expect(response.status).toBe(400);
    expect(appErrorResponseSchema.parse(await response.json()).error.code).toBe('VALIDATION_ERROR');
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

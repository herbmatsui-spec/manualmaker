import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Hono } from 'hono';
import type { AppEnv, Env } from '../../lib/types';
import { registerUploadRoutes } from '../upload';
import { registerResultsRoutes } from '../results';
import { ValidationError, NotFoundError, ExternalAPIError, StorageError, RateLimitError } from '../../lib/errors';
import { correlationId, errorHandler } from '../../lib/middleware';
import { fetchWithRetry } from '../../lib/http-client';

function createTestApp() {
  const app = new Hono<AppEnv>();
  app.onError((error) => { throw error; });
  app.use('*', correlationId());
  app.use('*', errorHandler());
  return app;
}

const requestId = 'test-request-id';
const headers = { 'x-request-id': requestId };

describe('Error Handling', () => {
  let app: Hono<AppEnv>;

  beforeEach(() => {
    app = createTestApp();
  });

  it.each([
    [new ValidationError('Test validation error', { field: 'test' }), 400, 'VALIDATION_ERROR', 'Test validation error', { field: 'test' }],
    [new NotFoundError('Test resource'), 404, 'NOT_FOUND', 'Test resource not found', undefined],
    [new ExternalAPIError('gemini', 'Test external API error', 502), 502, 'EXTERNAL_API_ERROR', 'Test external API error', undefined],
    [new StorageError('Test storage error', { operation: 'write' }), 500, 'STORAGE_ERROR', 'Test storage error', { operation: 'write' }],
    [new RateLimitError(30), 429, 'RATE_LIMIT_EXCEEDED', 'Too many requests', { retryAfter: 30 }],
    [new Error('Test generic error'), 500, 'INTERNAL_ERROR', 'Internal server error', undefined]
  ] as const)('formats %s with status %i', async (error, status, code, message, details) => {
    app.get('/test/error', () => { throw error; });

    const res = await app.request('/test/error', { headers });
    expect(res.status).toBe(status);
    expect(res.headers.get('x-request-id')).toBe(requestId);
    expect(await res.json()).toEqual({
      error: { code, message, requestId, ...(details === undefined ? {} : { details }) }
    });
  });

  it('generates a correlation ID when none is provided', async () => {
    app.get('/test/error', () => { throw new NotFoundError('Test resource'); });
    const res = await app.request('/test/error');
    const id = res.headers.get('x-request-id');
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
    expect(await res.json()).toEqual({
      error: { code: 'NOT_FOUND', message: 'Test resource not found', requestId: id }
    });
  });

  it('handles missing files in the upload route', async () => {
    registerUploadRoutes(app);
    const env = { RATE_LIMIT_ENABLED: 'false' } as Env;
    const res = await app.request('/api/upload', { method: 'POST', headers }, env);
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({
      error: {
        code: 'VALIDATION_ERROR', message: 'Validation failed', requestId,
        details: [{ path: 'file', message: 'Input not instance of File', code: 'custom' }]
      }
    });
  });

  it('handles invalid file IDs in the results route', async () => {
    registerResultsRoutes(app);
    const res = await app.request('/api/results/invalid-file-id', { headers });
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({
      error: {
        code: 'VALIDATION_ERROR', message: 'Validation failed', requestId,
        details: [{ path: 'fileId', message: 'Invalid fileId format', code: 'invalid_string' }]
      }
    });
  });

  it('handles missing results for valid file IDs', async () => {
    registerResultsRoutes(app);
    const get = vi.fn().mockResolvedValue(null);
    const env = { PROCESSING_KV: { get } } as unknown as Env;
    const fileId = 'a'.repeat(32);
    const res = await app.request(`/api/results/${fileId}`, { headers }, env);
    expect(res.status).toBe(404);
    expect(await res.json()).toEqual({
      error: { code: 'NOT_FOUND', message: 'Result not found', requestId }
    });
    expect(get).toHaveBeenCalledExactlyOnceWith(`result:${fileId}`);
  });
});

describe('Retry Logic', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('retries retryable status codes', async () => {
    const mockFetch = vi.fn()
      .mockResolvedValueOnce(new Response('Internal Server Error', { status: 500 }))
      .mockResolvedValueOnce(new Response('Success', { status: 200 }));
    vi.stubGlobal('fetch', mockFetch);
    const options = { method: 'GET' };
    const response = await fetchWithRetry('http://localhost/api', options, {
      maxRetries: 3, baseDelayMs: 1, maxDelayMs: 10
    });
    expect(response.status).toBe(200);
    expect(await response.text()).toBe('Success');
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockFetch).toHaveBeenNthCalledWith(1, 'http://localhost/api', options);
    expect(mockFetch).toHaveBeenNthCalledWith(2, 'http://localhost/api', options);
  });

  it('returns non-retryable responses without retrying', async () => {
    const mockFetch = vi.fn().mockResolvedValue(new Response('Not Found', { status: 404 }));
    vi.stubGlobal('fetch', mockFetch);
    const response = await fetchWithRetry('http://localhost/api', { method: 'GET' });
    expect(response.status).toBe(404);
    expect(await response.text()).toBe('Not Found');
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('throws the last error after max retries are exhausted', async () => {
    const mockFetch = vi.fn().mockResolvedValue(new Response('Internal Server Error', { status: 500 }));
    vi.stubGlobal('fetch', mockFetch);
    await expect(fetchWithRetry('http://localhost/api', { method: 'GET' }, {
      maxRetries: 2, baseDelayMs: 1, maxDelayMs: 10
    })).rejects.toThrow('HTTP 500');
    expect(mockFetch).toHaveBeenCalledTimes(3);
  });
});

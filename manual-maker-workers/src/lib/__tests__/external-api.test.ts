import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createGeminiApi, createVisionApi } from '../external-api';
import { fetchWithRetry } from '../http-client';
import { CircuitState } from '../circuit-breaker';
import { ExternalAPIError } from '../errors';
import type { Env } from '../types';

vi.mock('../http-client', () => ({ fetchWithRetry: vi.fn() }));

const fetchMock = vi.mocked(fetchWithRetry);
const get = vi.fn();
const put = vi.fn();
const env = {
  GEMINI_MODEL_NAME: 'test-model',
  GEMINI_API_KEY: 'test-key',
  GOOGLE_API_KEY: 'vision-test-key',
  PROCESSING_KV: { get, put },
} as unknown as Env;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-09-17T00:00:00Z'));
  vi.resetAllMocks();
  get.mockResolvedValue(null);
  put.mockResolvedValue(undefined);
});
afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
});

const operations = [
  {
    name: 'Gemini content',
    create: () => createGeminiApi(env),
    call: (api: ReturnType<typeof createGeminiApi>) => api.generateContent({ contents: [{ parts: [{ text: 'hello' }] }] }),
    key: 'gemini:test-model:generateContent',
    method: 'POST',
    url: 'https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent',
    threshold: 5,
  },
  {
    name: 'Gemini models',
    create: () => createGeminiApi(env),
    call: (api: ReturnType<typeof createGeminiApi>) => api.listModels(),
    key: 'gemini:test-model:listModels',
    method: 'GET',
    url: 'https://generativelanguage.googleapis.com/v1beta/models',
    threshold: 5,
  },
];

for (const operation of operations) {
  describe(operation.name, () => {
    it('returns and caches the upstream JSON response', async () => {
      fetchMock.mockResolvedValue(Response.json({ result: 'ok' }));
      const api = operation.create();
      expect(await operation.call(api)).toEqual({ result: 'ok' });
      expect(fetchMock).toHaveBeenCalledWith(operation.url, expect.objectContaining({ method: operation.method }), { maxRetries: 2 });
      expect(put).toHaveBeenCalledWith(expect.stringMatching(/^fallback:gemini:v2:[a-f0-9]{64}$/), '{"result":"ok"}', { expirationTtl: 300 });
      expect(fetchMock.mock.calls[0][1].headers).toMatchObject({ 'x-goog-api-key': 'test-key' });
      expect(api.getCircuitState()).toBe(CircuitState.CLOSED);
      expect(api.getCircuitMetrics()).toMatchObject({ failureCount: 0, name: 'gemini-api' });
    });

    it('preserves the upstream response when cache persistence fails', async () => {
      put.mockRejectedValue(new Error('KV unavailable'));
      fetchMock.mockResolvedValue(Response.json({ result: 'ok' }));
      expect(await operation.call(operation.create())).toEqual({ result: 'ok' });
    });

    it('reports failures and supports manual recovery', async () => {
      fetchMock.mockImplementation(async () => new Response('unavailable', { status: 503 }));
      const api = operation.create();
      for (let i = 0; i < operation.threshold; i++) {
        await expect(operation.call(api)).rejects.toBeInstanceOf(ExternalAPIError);
      }
      expect(api.getCircuitState()).toBe(CircuitState.OPEN);
      expect(api.getCircuitMetrics().failureCount).toBe(operation.threshold);
      api.resetCircuitBreaker();
      expect(api.getCircuitState()).toBe(CircuitState.CLOSED);
      expect(api.getCircuitMetrics().failureCount).toBe(0);
    });
  });
}

describe('request-scoped fallback', () => {
  it('serves only the matching input while OPEN, without further upstream requests', async () => {
    const stored = new Map<string, string>();
    put.mockImplementation(async (key, value) => { stored.set(key, value); });
    get.mockImplementation(async key => stored.get(key) ?? null);
    const api = createGeminiApi(env);
    const a = { contents: [{ parts: [{ text: 'input A' }] }] };
    const b = { contents: [{ parts: [{ text: 'input B' }] }] };
    fetchMock.mockResolvedValueOnce(Response.json({ output: 'A' }));
    await api.generateContent(a);
    fetchMock.mockImplementation(async () => new Response('failure', { status: 403 }));
    for (let i = 0; i < 5; i++) await expect(api.generateContent(b)).rejects.toBeInstanceOf(ExternalAPIError);
    const calls = fetchMock.mock.calls.length;
    await expect(api.generateContent(a)).resolves.toEqual({ output: 'A' });
    await expect(api.generateContent(b)).rejects.toMatchObject({ name: 'CircuitBreakerOpenError' });
    expect(fetchMock).toHaveBeenCalledTimes(calls);
    expect(api.getCircuitState()).toBe(CircuitState.OPEN);
  });
});

describe('Vision API', () => {
  const request = { requests: [{ image: { content: 'aGVsbG8=' }, features: [{ type: 'TEXT_DETECTION' }] }] };

  it('sends the image request and caches the result', async () => {
    fetchMock.mockResolvedValue(Response.json({ responses: [{ text: 'hello' }] }));
    const api = createVisionApi(env);
    expect(await api.annotateImage(request)).toEqual({ responses: [{ text: 'hello' }] });
    expect(fetchMock).toHaveBeenCalledWith('https://vision.googleapis.com/v1/images:annotate', expect.objectContaining({ method: 'POST', body: JSON.stringify(request) }), { maxRetries: 2 });
    expect(put).toHaveBeenCalledWith(expect.stringMatching(/^fallback:vision:v2:[a-f0-9]{64}$/), JSON.stringify({ responses: [{ text: 'hello' }] }), { expirationTtl: 300 });
    expect(fetchMock.mock.calls[0][1].headers).toMatchObject({ 'x-goog-api-key': 'vision-test-key' });
    expect(api.getCircuitState()).toBe(CircuitState.CLOSED);
    expect(api.getCircuitMetrics()).toMatchObject({ failureCount: 0, name: 'vision-api' });
  });

  it('returns successful responses despite cache failure', async () => {
    put.mockRejectedValue(new Error('KV unavailable'));
    fetchMock.mockResolvedValue(Response.json({ responses: [] }));
    expect(await createVisionApi(env).annotateImage(request)).toEqual({ responses: [] });
  });

  it('opens after repeated errors and resets', async () => {
    fetchMock.mockImplementation(async () => new Response('bad request', { status: 400 }));
    const api = createVisionApi(env);
    for (let i = 0; i < 3; i++) await expect(api.annotateImage(request)).rejects.toBeInstanceOf(ExternalAPIError);
    expect(api.getCircuitState()).toBe(CircuitState.OPEN);
    expect(api.getCircuitMetrics().failureCount).toBe(3);
    api.resetCircuitBreaker();
    expect(api.getCircuitMetrics()).toMatchObject({ state: CircuitState.CLOSED, failureCount: 0 });
  });
});

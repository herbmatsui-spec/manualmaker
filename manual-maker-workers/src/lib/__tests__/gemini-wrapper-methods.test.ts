import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createGeminiApi } from '../external-api';
import { fetchWithRetry } from '../http-client';
import type { Env } from '../types';

vi.mock('../http-client', () => ({ fetchWithRetry: vi.fn() }));
const upstream = vi.mocked(fetchWithRetry);
const put = vi.fn();
const env = { GEMINI_API_KEY: 'test', PROCESSING_KV: { put, get: vi.fn().mockResolvedValue(null) } } as unknown as Env;
beforeEach(() => { vi.clearAllMocks(); put.mockResolvedValue(undefined); });
afterEach(() => vi.restoreAllMocks());

describe('C05 Gemini model methods', () => {
  it.each(['generateContent', 'streamGenerateContent', 'countTokens'])('forwards arbitrary JSON with %s and a dynamic model', async method => {
    const body = { contents: [], extraProviderOption: { enabled: true } };
    const result = method === 'streamGenerateContent' ? [{ candidates: [] }] : { totalTokens: 3 };
    upstream.mockResolvedValueOnce(Response.json(result));
    expect(await createGeminiApi(env).callModel('gemini-2.0-flash', method, body)).toEqual(result);
    expect(upstream).toHaveBeenCalledWith(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:${method}`,
      expect.objectContaining({ method: 'POST', body: JSON.stringify(body), signal: expect.any(AbortSignal), headers: {
        'Content-Type': 'application/json', 'x-goog-api-key': 'test',
      } }), { maxRetries: 2 },
    );
  });
  it.each([['invalid/model', 'generateContent'], ['gemini-2.0-flash', 'unknown']])('rejects unapproved parameters %s/%s before I/O', async (model, method) => {
    await expect(createGeminiApi(env).callModel(model, method, {})).rejects.toMatchObject({ name: 'ZodError' });
    expect(upstream).not.toHaveBeenCalled();
    expect(put).not.toHaveBeenCalled();
  });
  it('separates cache entries by model and method', async () => {
    upstream.mockImplementation(async () => Response.json({ ok: true }));
    const api = createGeminiApi(env);
    await api.callModel('model-a', 'generateContent', {});
    await api.callModel('model-b', 'generateContent', {});
    await api.callModel('model-a', 'countTokens', {});
    await api.callModel('model-a', 'streamGenerateContent', {});
    await api.listModels();
    expect(new Set(put.mock.calls.map(call => call[0])).size).toBe(5);
  });
});

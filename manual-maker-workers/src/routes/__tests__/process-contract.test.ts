import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApp } from '../../app';
import { processingResponseSchema, appErrorResponseSchema } from '../openapi';
import type { Env } from '../../lib/types';

const fileId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const state = { fileId, status: 'processing', progress: 25, stage: 'OCR', updatedAt: '2026-09-17T00:00:00.000Z' };
function setup(fallback = false) {
  const updateProgress = vi.fn().mockResolvedValue(undefined);
  const queryProgress = vi.fn().mockResolvedValue(state);
  if (fallback) {
    updateProgress.mockRejectedValue(new Error('DO unavailable'));
    queryProgress.mockResolvedValue(null);
  }
  const get = vi.fn(async (key: string, type?: 'text' | 'json') => {
    const value = key.startsWith('uploaded:') ? { path: 'upload.pdf' } : state;
    return type === 'json' ? value : JSON.stringify(value);
  });
  const put = vi.fn().mockResolvedValue(undefined);
  const env = { RATE_LIMIT_ENABLED: 'false', PROCESSING_KV: { get, put },
    PROGRESS_DO: { idFromName: (name: string) => name, get: () => ({ updateProgress, queryProgress }) },
  } as unknown as Env;
  return { app: createApp(), env, get, put, updateProgress, queryProgress };
}
afterEach(() => vi.restoreAllMocks());

describe('P9 processing contracts', () => {
  it.each([false, true])('validates start, update and query with KV fallback=%s', async fallback => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const s = setup(fallback);
    const docResponse = await s.app.request('/api/doc', undefined, s.env);
    const doc = await docResponse.json() as { paths: Record<string, Record<string, {
      requestBody?: { content: Record<string, { schema: { required: string[] } }> };
      responses: Record<string, unknown>;
    }>> };
    const cases = [
      { method: 'POST', path: `/api/process/${fileId}`, specPath: '/api/process/{fileId}', body: { options: {} }, progress: 0, required: 'options' },
      { method: 'PUT', path: `/api/process/${fileId}/progress`, specPath: '/api/process/{fileId}/progress', body: { progress: 75, stage: 'Formatting' }, progress: 75, required: 'progress' },
      { method: 'GET', path: `/api/process/${fileId}`, specPath: '/api/process/{fileId}', progress: 25 },
    ];
    for (const item of cases) {
      const contract = doc.paths[item.specPath][item.method.toLowerCase()];
      expect(contract.responses['200']).toBeDefined();
      if (item.required) expect(contract.requestBody?.content['application/json'].schema.required).toContain(item.required);
      const response = await s.app.request(item.path, { method: item.method,
        ...(item.body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(item.body) } : {}),
      }, s.env);
      expect(response.status).toBe(200);
      expect(processingResponseSchema.parse(await response.json())).toMatchObject({ fileId, progress: item.progress });
    }
    expect(s.put).toHaveBeenCalledTimes(fallback ? 2 : 0);
  });

  it('rejects invalid progress before accessing storage', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = setup();
    const response = await s.app.request(`/api/process/${fileId}/progress`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ progress: 101 }),
    }, s.env);
    expect(response.status).toBe(400);
    expect(appErrorResponseSchema.parse(await response.json()).error.code).toBe('VALIDATION_ERROR');
    expect(s.queryProgress).not.toHaveBeenCalled();
    expect(s.put).not.toHaveBeenCalled();
  });

  it('returns a structured 404 when neither state store contains the process', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = setup(); s.queryProgress.mockResolvedValue(null); s.get.mockResolvedValue(null as never);
    const response = await s.app.request(`/api/process/${fileId}`, undefined, s.env);
    expect(response.status).toBe(404);
    expect(appErrorResponseSchema.parse(await response.json()).error.code).toBe('NOT_FOUND');
  });
});

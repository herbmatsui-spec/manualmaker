import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApp } from '../../app';
import { appErrorResponseSchema, resultResponseSchema } from '../openapi';
import type { Env } from '../../lib/types';

const fileId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const meta = { fileId, path: `results/${fileId}/manual.md`, size: 4,
  title: '手順', savedAt: '2026-09-17T00:00:00.000Z' };

afterEach(() => vi.restoreAllMocks());

describe('P9 result-get contract', () => {
  it('publishes both result operations and structured errors', async () => {
    const app = createApp();
    const response = await app.request('/api/doc', undefined, { RATE_LIMIT_ENABLED: 'false' } as Env);
    expect(response.status).toBe(200);
    const doc = await response.json() as { paths: Record<string, {
      get: { responses: Record<string, unknown> }; post: unknown;
    }> };
    const path = doc.paths['/api/results/{fileId}'];
    expect(path.post).toBeDefined();
    expect(path.get.responses['200']).toMatchObject({ content: { 'application/json': {
      schema: { required: ['fileId', 'path', 'size', 'title', 'savedAt', 'markdown'] },
    } } });
    expect(path.get.responses['404']).toMatchObject({ content: { 'application/json': {
      schema: { required: ['error'], properties: { error: { required: ['code', 'message', 'requestId'] } } },
    } } });
  });

  it('validates actual metadata and Markdown without changing the response', async () => {
    const get = vi.fn().mockResolvedValue({ text: async () => '# 手順' });
    const env = { RATE_LIMIT_ENABLED: 'false', BUCKET: { get },
      PROCESSING_KV: { get: vi.fn().mockResolvedValue(JSON.stringify(meta)) },
    } as unknown as Env;
    const response = await createApp().request(`/api/results/${fileId}`, undefined, env);
    expect(response.status).toBe(200);
    expect(resultResponseSchema.parse(await response.json())).toEqual({ ...meta, markdown: '# 手順' });
    expect(get).toHaveBeenCalledExactlyOnceWith(meta.path);
  });

  it.each(['metadata', 'body'])('returns a documented 404 for missing %s', async missing => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const get = vi.fn().mockResolvedValue(null);
    const env = { RATE_LIMIT_ENABLED: 'false', BUCKET: { get },
      PROCESSING_KV: { get: vi.fn().mockResolvedValue(missing === 'metadata' ? null : JSON.stringify(meta)) },
    } as unknown as Env;
    const response = await createApp().request(`/api/results/${fileId}`, undefined, env);
    expect(response.status).toBe(404);
    const body = appErrorResponseSchema.parse(await response.json());
    expect(body.error.code).toBe('NOT_FOUND');
    expect(body.error.requestId).toBe(response.headers.get('x-request-id'));
    if (missing === 'metadata') expect(get).not.toHaveBeenCalled();
  });
});

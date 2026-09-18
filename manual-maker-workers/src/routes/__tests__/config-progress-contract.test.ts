import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApp } from '../../app';
import { processingResponseSchema } from '../openapi';
import type { Env } from '../../lib/types';

const fileId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const state = { fileId, status: 'processing', progress: 40, stage: 'OCR', updatedAt: '2026-09-17T00:00:00.000Z' };

const { getByPrefix } = vi.hoisted(() => ({ getByPrefix: vi.fn() }));
vi.mock('../../lib/kv-batch', () => ({ createKVBatch: () => ({ getByPrefix }) }));

function setup() {
  const queryProgress = vi.fn().mockResolvedValue(state);
  const env = { RATE_LIMIT_ENABLED: 'false', GEMINI_MODEL_NAME: 'gemini-1.5-flash',
    PROCESSING_KV: { get: vi.fn(), put: vi.fn() },
    PROGRESS_DO: { idFromName: (name: string) => name, get: () => ({ queryProgress }) },
  } as unknown as Env;
  return { app: createApp(), env, queryProgress };
}
afterEach(() => { vi.restoreAllMocks(); getByPrefix.mockReset(); });

describe('P9 config, process list and progress contracts', () => {
  it('returns the documented configuration', async () => {
    const s = setup();
    const response = await s.app.request('/api/config', undefined, s.env);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      geminiModelName: 'gemini-1.5-flash', processorType: 'cloudflare-workers', pdfDpi: 300,
      maxFileSizeMb: 50, webUploadMaxMb: 100, outputDirectory: 'r2://manual-processor-files',
      supportedExtensions: ['.pdf'], defaultLanguage: 'ja',
    });
  });

  it('lists only KV fallback states', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = setup();
    getByPrefix.mockResolvedValue({ [`process:${fileId}`]: state });
    const response = await s.app.request('/api/processes', undefined, s.env);
    expect(response.status).toBe(200);
    const body = await response.json() as { processes: unknown[] };
    expect(body.processes).toHaveLength(1);
    expect(processingResponseSchema.parse(body.processes[0])).toMatchObject({ fileId, progress: 40 });
    expect(getByPrefix).toHaveBeenCalledExactlyOnceWith('process:');
    expect(s.queryProgress).not.toHaveBeenCalled();
  });

  it('rejects an invalid progress identifier before querying the DO', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = setup();
    const response = await s.app.request('/api/progress/invalid/http', undefined, s.env);
    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({ error: { code: 'VALIDATION_ERROR' } });
    expect(s.queryProgress).not.toHaveBeenCalled();
  });

  it('returns a structured, sanitized 500 when the DO query fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = setup();
    s.queryProgress.mockRejectedValue(new Error('internal storage details'));
    const response = await s.app.request(`/api/progress/${fileId}/http`, undefined, s.env);
    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({ error: {
      code: 'INTERNAL_ERROR', message: 'Internal server error',
      requestId: response.headers.get('x-request-id'),
    } });
  });

  it('serves progress over HTTP and documents the missing state', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = setup();
    const docResponse = await s.app.request('/api/doc', undefined, s.env);
    const doc = await docResponse.json() as { paths: Record<string, { get: { responses: Record<string, unknown> } }> };
    expect(doc.paths['/api/progress/{fileId}/http'].get.responses['404']).toMatchObject({
      content: { 'application/json': { schema: { required: ['error'] } } },
    });
    const response = await s.app.request(`/api/progress/${fileId}/http`, undefined, s.env);
    expect(response.status).toBe(200);
    expect(processingResponseSchema.parse(await response.json())).toMatchObject({ fileId, progress: 40 });
    expect(s.queryProgress).toHaveBeenCalledTimes(1);
    s.queryProgress.mockResolvedValue(null);
    const missing = await s.app.request(`/api/progress/${fileId}/http`, undefined, s.env);
    expect(missing.status).toBe(404);
    expect(await missing.json()).toMatchObject({ error: { code: 'NOT_FOUND' } });
  });
});

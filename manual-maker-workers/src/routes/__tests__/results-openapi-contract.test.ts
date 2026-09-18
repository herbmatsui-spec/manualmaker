import { describe, expect, it, vi } from 'vitest';
import { resultSaveResponseSchema } from '../openapi';
import { createApp } from '../../app';
import type { Env } from '../../lib/types';

describe('P9 result-save OpenAPI contract', () => {
  it('validates the actual saved result and storage writes', async () => {
    const put = vi.fn().mockResolvedValue({});
    const metadataPut = vi.fn().mockResolvedValue(undefined);
    const env = {
      RATE_LIMIT_ENABLED: 'false', BUCKET: { put },
      PROCESSING_KV: { put: metadataPut, get: vi.fn().mockResolvedValue(null) },
    } as unknown as Env;
    const fileId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
    const response = await createApp().request(`/api/results/${fileId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ markdown: '# Manual', title: 'Manual' }),
    }, env);
    expect(response.status).toBe(200);
    expect(resultSaveResponseSchema.parse(await response.json())).toEqual({
      success: true, fileId, path: `results/${fileId}/manual.md`,
    });
    expect(put).toHaveBeenCalledExactlyOnceWith(`results/${fileId}/manual.md`, '# Manual', {
      httpMetadata: { contentType: 'text/markdown; charset=utf-8' },
    });
    expect(metadataPut).toHaveBeenCalledTimes(1);
    expect(JSON.parse(metadataPut.mock.calls[0][1])).toMatchObject({ fileId, title: 'Manual', size: 8 });
  });

  it('rejects empty markdown before persistence', async () => {
    const put = vi.fn();
    const env = { RATE_LIMIT_ENABLED: 'false', BUCKET: { put }, PROCESSING_KV: { put } } as unknown as Env;
    const response = await createApp().request('/api/results/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ markdown: '' }),
    }, env);
    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({ error: { code: 'VALIDATION_ERROR' } });
    expect(put).not.toHaveBeenCalled();
  });

  it('documents POST /api/results/{fileId} request and success response', async () => {
    const app = createApp();
    const env = { RATE_LIMIT_ENABLED: 'false' } as Env;
    const response = await app.request('/api/doc', undefined, env);
    expect(response.status).toBe(200);
    const document = await response.json() as {
      paths: Record<string, { post?: {
        parameters?: unknown;
        requestBody?: unknown;
        responses: Record<string, unknown>;
      } }>;
    };
    const operation = document.paths['/api/results/{fileId}']?.post;
    expect(operation, 'Result-save route must be included in the published specification').toBeDefined();
    if (!operation) throw new Error('Result-save contract is missing');
    expect(operation.parameters).toEqual(expect.arrayContaining([
      expect.objectContaining({ name: 'fileId', in: 'path', required: true }),
    ]));
    expect(operation.requestBody).toMatchObject({
      required: true,
      content: { 'application/json': { schema: {
        type: 'object', required: ['markdown'],
        properties: { markdown: { type: 'string', minLength: 1, maxLength: 10 * 1024 * 1024 } },
      } } },
    });
    expect(operation.responses['200']).toMatchObject({
      content: { 'application/json': { schema: {
        type: 'object', required: ['success', 'fileId', 'path'],
        properties: { success: { type: 'boolean', enum: [true] }, fileId: { type: 'string' }, path: { type: 'string' } },
      } } },
    });
  });
});

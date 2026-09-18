import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApp } from '../../app';
import { appErrorResponseSchema, uploadResponseSchema } from '../openapi';
import type { Env } from '../../lib/types';

// Isolate the already-tested batch cache; exercise real routes and app middleware.
const { getByPrefix } = vi.hoisted(() => ({ getByPrefix: vi.fn() }));
vi.mock('../../lib/kv-batch', () => ({ createKVBatch: () => ({ getByPrefix }) }));

const fileId = '550e8400-e29b-41d4-a716-446655440000';
const metadata = { fileId, filename: 'manual.pdf', sizeMb: 1,
  path: `uploads/${fileId}/manual.pdf`, uploadedAt: '2026-09-17T00:00:00.000Z' };

function setup() {
  const get = vi.fn().mockResolvedValue(JSON.stringify(metadata));
  const deleteObject = vi.fn().mockResolvedValue(undefined);
  const deleteMetadata = vi.fn().mockResolvedValue(undefined);
  const env = { RATE_LIMIT_ENABLED: 'false', BUCKET: { delete: deleteObject },
    PROCESSING_KV: { get, delete: deleteMetadata },
  } as unknown as Env;
  return { app: createApp(), env, get, deleteObject, deleteMetadata };
}

afterEach(() => { vi.restoreAllMocks(); getByPrefix.mockReset(); });

describe('P9 upload list and delete contracts', () => {
  it('publishes list and delete success schemas and delete error schemas', async () => {
    const s = setup();
    const response = await s.app.request('/api/doc', undefined, s.env);
    expect(response.status).toBe(200);
    const doc = await response.json() as { paths: Record<string, Record<string, {
      parameters?: unknown[]; responses: Record<string, unknown>;
    }>> };
    expect(doc.paths['/api/uploads'].get.responses['200']).toMatchObject({
      content: { 'application/json': { schema: { type: 'object', required: ['uploads'],
        properties: { uploads: { type: 'array', items: { type: 'object',
          required: ['fileId', 'filename', 'sizeMb', 'path', 'uploadedAt'] } } },
      } } },
    });
    const deletion = doc.paths['/api/uploads/{fileId}'].delete;
    expect(deletion.parameters).toContainEqual(expect.objectContaining({ name: 'fileId', in: 'path', required: true }));
    expect(deletion.responses['200']).toMatchObject({ content: { 'application/json': {
      schema: { type: 'object', required: ['success', 'fileId'],
        properties: { success: { type: 'boolean', enum: [true] }, fileId: { type: 'string' } } },
    } } });
    for (const status of ['400', '404']) {
      expect(deletion.responses[status]).toMatchObject({ content: { 'application/json': {
        schema: { required: ['error'], properties: { error: { required: ['code', 'message', 'requestId'] } } },
      } } });
    }
  });

  it.each([false, true])('returns a schema-valid upload list, empty=%s', async empty => {
    const s = setup();
    getByPrefix.mockResolvedValue(empty ? {} : { [`uploaded:${fileId}`]: metadata });
    const response = await s.app.request('/api/uploads', undefined, s.env);
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body).toEqual({ uploads: empty ? [] : [metadata] });
    const uploads = (body as { uploads: unknown[] }).uploads;
    for (const upload of uploads) expect(uploadResponseSchema.parse(upload)).toEqual(metadata);
    expect(getByPrefix).toHaveBeenCalledExactlyOnceWith('uploaded:');
    expect(s.deleteObject).not.toHaveBeenCalled();
    expect(s.deleteMetadata).not.toHaveBeenCalled();
  });

  it('deletes the object and metadata and returns the documented success body', async () => {
    const s = setup();
    const response = await s.app.request(`/api/uploads/${fileId}`, { method: 'DELETE' }, s.env);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ success: true, fileId });
    expect(s.get).toHaveBeenCalledExactlyOnceWith(`uploaded:${fileId}`);
    expect(s.deleteObject).toHaveBeenCalledExactlyOnceWith(metadata.path);
    expect(s.deleteMetadata).toHaveBeenCalledExactlyOnceWith(`uploaded:${fileId}`);
    expect(s.deleteObject.mock.invocationCallOrder[0]).toBeLessThan(s.deleteMetadata.mock.invocationCallOrder[0]);
  });

  it.each([
    [fileId, 404, 'NOT_FOUND'],
    ['invalid-id', 400, 'VALIDATION_ERROR'],
  ] as const)('rejects deletion of %s with %i and no writes', async (id, status, code) => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = setup(); s.get.mockResolvedValue(null);
    const response = await s.app.request(`/api/uploads/${id}`, { method: 'DELETE' }, s.env);
    expect(response.status).toBe(status);
    const body = appErrorResponseSchema.parse(await response.json());
    expect(body.error.code).toBe(code);
    expect(body.error.requestId).toBe(response.headers.get('x-request-id'));
    expect(s.deleteObject).not.toHaveBeenCalled();
    expect(s.deleteMetadata).not.toHaveBeenCalled();
    if (status === 400) expect(s.get).not.toHaveBeenCalled();
  });
});

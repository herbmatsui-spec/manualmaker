import { describe, it, expect, beforeEach, vi } from 'vitest';
import { OpenAPIHono } from '@hono/zod-openapi';
import type { AppEnv, Env } from '../../lib/types';
import { registerRoutes } from '../index';
import { healthResponseSchema, uploadResponseSchema } from '../openapi';

const put = vi.fn(async (_key: string, stream: ReadableStream<Uint8Array>) => {
  await stream.pipeTo(new WritableStream<Uint8Array>({ write() {} }));
});
const metadataPut = vi.fn();
const env = {
  BUCKET: { put },
  PROCESSING_KV: { put: metadataPut },
  RATE_LIMIT_ENABLED: 'false',
} as unknown as Env;

describe('OpenAPI Contract Testing', () => {
  let app: OpenAPIHono<AppEnv>;

  beforeEach(() => {
    vi.clearAllMocks();
    app = new OpenAPIHono<AppEnv>();
    registerRoutes(app);
  });

  it('should return valid OpenAPI document', async () => {
    const response = await app.request('/api/doc', undefined, env);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      openapi: '3.1.0',
      info: { title: 'Manual Maker API', version: '2.0.0' },
      paths: {
        '/api/upload': { post: { responses: { '200': {
          content: { 'application/json': { schema: {
            type: 'object',
            required: ['fileId', 'filename', 'sizeMb', 'path', 'uploadedAt'],
          } } },
        } } } },
        '/api/health': { get: { responses: { '200': {
          content: { 'application/json': { schema: {
            type: 'object', required: ['status', 'version', 'processorType'],
          } } },
        } } } },
      },
    });
  });

  it('should validate upload endpoint response against schema', async () => {
    const form = new FormData();
    form.append('file', new File(['%PDF-1.7\n'], 'test.pdf', { type: 'application/pdf' }));
    const response = await app.request('/api/upload', { method: 'POST', body: form }, env);
    expect(response.status).toBe(200);
    const metadata = uploadResponseSchema.parse(await response.json());
    expect(metadata.filename).toBe('test.pdf');
    expect(metadata.path).toBe(`uploads/${metadata.fileId}/test.pdf`);
    expect(metadata.sizeMb).toBe(0);
    expect(put).toHaveBeenCalledExactlyOnceWith(metadata.path, expect.any(ReadableStream), {
      httpMetadata: { contentType: 'application/pdf' },
    });
    expect(metadataPut).toHaveBeenCalledExactlyOnceWith(
      `uploaded:${metadata.fileId}`, JSON.stringify(metadata),
    );
  });

  it('should validate health endpoint response', async () => {
    const response = await app.request('/api/health', undefined, env);
    expect(response.status).toBe(200);
    expect(healthResponseSchema.parse(await response.json())).toEqual({
      status: 'ok', version: '2.0.0', processorType: 'cloudflare-workers',
    });
  });
});

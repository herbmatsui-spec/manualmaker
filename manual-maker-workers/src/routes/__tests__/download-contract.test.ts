import { describe, expect, it, vi } from 'vitest';
import { createApp } from '../../app';
import type { Env } from '../../lib/types';

type ResponseContract = {
  content?: Record<string, { schema: { type: string; format?: string } }>;
  headers?: Record<string, { schema: { type: string; pattern?: string; enum?: string[] } }>;
};

describe('P9 download published contract', () => {
  it.each([
    ['pdf', undefined, undefined, 200, 10],
    ['md', undefined, undefined, 200, 10],
    ['markdown', 'bytes=2-4', undefined, 206, 3],
    ['pdf', 'bytes=10-', undefined, 416, 0],
    ['md', undefined, '"fixture"', 304, 0],
  ] as const)('matches %s range=%s conditional=%s to status %i', async (type, range, etag, status, size) => {
    const fileId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
    const head = vi.fn().mockResolvedValue({ size: 10, httpEtag: '"fixture"' });
    const get = vi.fn(async (_key: string, options?: { range: { offset: number; length: number } }) => ({
      size: 10, httpEtag: '"fixture"',
      body: new Blob([new Uint8Array(options?.range.length ?? 10)]).stream(),
    }));
    const env = {
      RATE_LIMIT_ENABLED: 'false', BUCKET: { head, get },
      PROCESSING_KV: { get: vi.fn().mockResolvedValue(JSON.stringify({ path: 'uploads/fixture.pdf' })) },
    } as unknown as Env;
    const app = createApp();
    const specResponse = await app.request('/api/doc', undefined, env);
    expect(specResponse.status).toBe(200);
    const spec = await specResponse.json() as { paths: Record<string, { get: {
      parameters: Array<{ name: string; in: string; required?: boolean }>;
      responses: Record<string, ResponseContract>;
    } }> };
    const operation = spec.paths['/api/download/{fileId}/{type}'].get;
    expect(operation.parameters).toEqual(expect.arrayContaining([
      expect.objectContaining({ name: 'fileId', in: 'path', required: true }),
      expect.objectContaining({ name: 'type', in: 'path', required: true }),
      expect.objectContaining({ name: 'Range', in: 'header' }),
    ]));
    const headers = new Headers();
    if (range) headers.set('Range', range);
    if (etag) headers.set('If-None-Match', etag);
    const response = await app.request(`/api/download/${fileId}/${type}`, { headers }, env);
    expect(response.status).toBe(status);
    const contract = operation.responses[String(status)];
    expect(contract).toBeDefined();
    if (contract.content) {
      const media = response.headers.get('content-type')!.split(';')[0];
      expect(contract.content[media].schema).toMatchObject({ type: 'string', format: 'binary' });
    } else {
      expect([304, 416]).toContain(status);
    }
    for (const [name, { schema }] of Object.entries(contract.headers ?? {})) {
      const value = response.headers.get(name);
      expect(value, name).not.toBeNull();
      if (schema.pattern) expect(value).toMatch(new RegExp(schema.pattern));
      if (schema.enum) expect(schema.enum).toContain(value);
    }
    expect((await response.arrayBuffer()).byteLength).toBe(size);
    if (status === 416) expect(get).not.toHaveBeenCalled();
  });
});

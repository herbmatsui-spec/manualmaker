import { describe, expect, it, vi } from 'vitest';
import { Hono } from 'hono';
import type { AppEnv } from '../../lib/types';
import { registerDownloadRoutes } from '../download';

const path = '/api/download/550e8400-e29b-41d4-a716-446655440000/md';
function setup(size = 1000) {
  const head = vi.fn(async () => ({ size, httpEtag: '"test"' }));
  const get = vi.fn(async (_key: string, options?: { range: { offset: number; length: number } }) => ({
    size,
    httpEtag: '"test"',
    body: new Blob([new Uint8Array(options?.range.length ?? size)]).stream(),
    writeHttpMetadata: vi.fn(),
  }));
  const env = { BUCKET: { head, get } } as unknown as AppEnv['Bindings'];
  const app = new Hono<AppEnv>();
  registerDownloadRoutes(app);
  return { app, env, head, get };
}

describe('P4 step 3: download Range', () => {
  it.each([
    ['bytes=0-100', 0, 100],
    ['bytes=-100', 900, 999],
    ['bytes=500-', 500, 999],
    ['bytes=900-2000', 900, 999],
    ['bytes=-2000', 0, 999],
    ['bytes=0-0', 0, 0],
  ])('serves %s', async (range, start, end) => {
    const { app, env, get } = setup();
    const response = await app.request(path, { headers: { Range: range } }, env);
    expect(response.status).toBe(206);
    expect(response.headers.get('Content-Range')).toBe(`bytes ${start}-${end}/1000`);
    expect(response.headers.get('Accept-Ranges')).toBe('bytes');
    expect(response.headers.get('Content-Length')).toBe(String(end - start + 1));
    expect((await response.arrayBuffer()).byteLength).toBe(end - start + 1);
    expect(get).toHaveBeenCalledWith(expect.any(String), { range: { offset: start, length: end - start + 1 } });
  });

  it.each(['bytes=1000-', 'bytes=10-5', 'bytes=-0', 'bytes=-', 'bytes=0-1,3-4', 'items=0-1', 'bytes=9007199254740992-', 'invalid', ''])('rejects invalid range %s', async (range) => {
    const { app, env, get } = setup();
    const response = await app.request(path, { headers: { Range: range } }, env);
    expect(response.status).toBe(416);
    expect(response.headers.get('Content-Range')).toBe('bytes */1000');
    expect(get).not.toHaveBeenCalled();
  });

  it('rejects ranges on an empty file', async () => {
    const { app, env } = setup(0);
    const response = await app.request(path, { headers: { Range: 'bytes=0-' } }, env);
    expect(response.status).toBe(416);
    expect(response.headers.get('Content-Range')).toBe('bytes */0');
  });

  it('returns a complete stream without Range', async () => {
    const { app, env, head, get } = setup();
    const response = await app.request(path, undefined, env);
    expect(get).toHaveBeenCalledTimes(1);
    expect(head).not.toHaveBeenCalled();
    expect(response.body).toBe((await get.mock.results[0].value).body);
    expect(response.status).toBe(200);
    expect(response.headers.get('Content-Length')).toBe('1000');
    expect(response.headers.get('Content-Range')).toBeNull();
    expect((await response.arrayBuffer()).byteLength).toBe(1000);
  });
});

import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApp } from '../../app';
import type { Env } from '../../lib/types';

function setup() {
  const put = vi.fn(async (_key: string, body: ReadableStream<Uint8Array>) => {
    await body.pipeTo(new WritableStream({ write() {} }));
    return {};
  });
  const get = vi.fn(async () => ({
    body: new Blob(['%PDF-test']).stream(),
    httpMetadata: { contentType: 'application/pdf' }, customMetadata: {},
  }));
  const replicaPut = vi.fn(async (_key: string, body: ReadableStream<Uint8Array>) => {
    await body.pipeTo(new WritableStream({ write() {} }));
    return {};
  });
  const metadataPut = vi.fn(async () => {});
  const env = {
    RATE_LIMIT_ENABLED: 'false', BUCKET: { put, get },
    BUCKET_SECONDARY: { put: replicaPut }, PROCESSING_KV: { put: metadataPut },
  } as unknown as Env;
  const pending: Promise<unknown>[] = [];
  const context = { props: {}, waitUntil: vi.fn((task: Promise<unknown>) => { pending.push(task); }), passThroughOnException() {} };
  const request = () => {
    const form = new FormData();
    form.append('file', new File(['%PDF-test'], 'manual.pdf', { type: 'application/pdf' }));
    return createApp().request('/api/upload', { method: 'POST', body: form }, env, context);
  };
  return { request, put, get, replicaPut, metadataPut, pending, context, env };
}

afterEach(() => vi.restoreAllMocks());

describe('P7 upload replication integration', () => {
  it('returns success before the tracked replica finishes', async () => {
    const s = setup();
    let finish!: () => void;
    const gate = new Promise<void>(resolve => { finish = resolve; });
    s.replicaPut.mockImplementation(async (_key, body) => {
      await gate;
      await body.pipeTo(new WritableStream({ write() {} }));
      return {};
    });
    try {
      const response = await s.request();
      expect(response.status).toBe(200);
      expect(s.context.waitUntil).toHaveBeenCalledTimes(1);
      expect(s.metadataPut).toHaveBeenCalledTimes(1);
      const metadata = await response.json() as { path: string };
      expect(s.get).toHaveBeenCalledWith(metadata.path);
    } finally { finish(); await Promise.all(s.pending); }
  });
  it('logs replica failure without rejecting background work or upload success', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = setup(); s.replicaPut.mockRejectedValue(new Error('replica unavailable'));
    expect((await s.request()).status).toBe(200);
    await Promise.all(s.pending);
    expect(log).toHaveBeenCalledWith(expect.stringContaining('r2_replication_failed'));
  });
  it.each(['primary', 'metadata'])('does not replicate when %s persistence fails', async failure => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = setup();
    if (failure === 'primary') s.put.mockRejectedValue(new Error('primary unavailable'));
    else s.metadataPut.mockRejectedValue(new Error('metadata unavailable'));
    expect((await s.request()).status).toBe(500);
    expect(s.context.waitUntil).not.toHaveBeenCalled();
    expect(s.get).not.toHaveBeenCalled();
  });
  it('skips replication when the secondary binding is absent', async () => {
    const s = setup(); delete s.env.BUCKET_SECONDARY;
    expect((await s.request()).status).toBe(200);
    expect(s.context.waitUntil).not.toHaveBeenCalled();
    expect(s.get).not.toHaveBeenCalled();
  });
});

import { afterEach, describe, expect, it, vi } from 'vitest';
import { Hono } from 'hono';
import type { AppEnv, UploadedFile } from '../../lib/types';
import { AppError } from '../../lib/errors';

// Listing uploads is outside this suite; avoid the unrelated broken memory-cache module.
vi.mock('../../lib/kv-batch', () => ({ createKVBatch: vi.fn() }));
import { registerUploadRoutes } from '../upload';

const MiB = 1024 * 1024;

function setup(maxMb = '100') {
  let storedSize = 0;
  const put = vi.fn(async (_key: string, stream: ReadableStream<Uint8Array>) => {
    expect(stream).toBeInstanceOf(ReadableStream);
    const reader = stream.getReader();
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        storedSize += value.byteLength;
      }
    } finally {
      reader.releaseLock();
    }
    return {};
  });
  const metadataPut = vi.fn(async () => undefined);
  const env = {
    BUCKET: { put },
    PROCESSING_KV: { put: metadataPut },
    RATE_LIMIT_ENABLED: 'false',
    WEB_UPLOAD_MAX_MB: maxMb,
  } as unknown as AppEnv['Bindings'];
  const app = new Hono<AppEnv>();
  app.onError((error, c) => c.json(
    { error: error.message },
    error instanceof AppError && error.statusCode === 413 ? 413 : 500,
  ));
  registerUploadRoutes(app);
  return { app, env, put, metadataPut, storedSize: () => storedSize };
}

function upload(size: number) {
  const form = new FormData();
  form.append('file', new File([new Uint8Array(size)], 'manual.pdf', {
    type: 'application/pdf',
  }));
  return new Request('http://localhost/api/upload', { method: 'POST', body: form });
}

afterEach(() => vi.restoreAllMocks());

describe('P4 step 1: multipart upload to R2 stream', () => {
  it.each([1024, 99 * MiB, 100 * MiB])('streams a %i-byte PDF and saves metadata', async (size) => {
    const { app, env, put, metadataPut, storedSize } = setup();
    const response = await app.request(upload(size), undefined, env);
    expect(response.status).toBe(200);
    expect(storedSize()).toBe(size);
    expect(put).toHaveBeenCalledTimes(1);
    const metadata = await response.json() as UploadedFile;
    expect(metadata.sizeMb).toBe(Math.round(size / MiB * 100) / 100);
    expect(metadata.filename).toBe('manual.pdf');
    expect(metadataPut).toHaveBeenCalledWith(`uploaded:${metadata.fileId}`, JSON.stringify(metadata));
  }, 20_000);

  it('uses File.stream rather than File.arrayBuffer in the storage handler', async () => {
    const { app, env } = setup();
    const request = upload(1024);
    // The native multipart parser may buffer internally; this assertion concerns the route only.
    const arrayBuffer = vi.spyOn(File.prototype, 'arrayBuffer').mockRejectedValue(new Error('Do not buffer File'));
    const stream = vi.spyOn(File.prototype, 'stream');
    const response = await app.request(request, undefined, env);
    expect(response.status).toBe(200);
    expect(stream).toHaveBeenCalled();
    expect(arrayBuffer).not.toHaveBeenCalled();
  });

  it('rejects one byte above the configured limit before either storage write', async () => {
    const { app, env, put, metadataPut } = setup('1');
    const response = await app.request(upload(MiB + 1), undefined, env);
    expect(response.status).toBe(413);
    expect(put).not.toHaveBeenCalled();
    expect(metadataPut).not.toHaveBeenCalled();
  });

  it('does not publish metadata when R2 storage fails', async () => {
    const { app, env, put, metadataPut } = setup();
    put.mockRejectedValueOnce(new Error('R2 unavailable'));
    const response = await app.request(upload(1024), undefined, env);
    expect(response.status).toBe(500);
    expect(metadataPut).not.toHaveBeenCalled();
  });
});

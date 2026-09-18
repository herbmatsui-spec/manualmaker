import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApp } from '../../app';
import { appErrorResponseSchema } from '../openapi';
import type { Env } from '../../lib/types';

const path = '/api/vision/annotate';
const env = { RATE_LIMIT_ENABLED: 'false', GOOGLE_API_KEY: 'test-only-key' } as Env;
const annotation = { image: { content: 'aW1hZ2U=' }, features: [{ type: 'TEXT_DETECTION' }] };
const request = (body: unknown) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('P9 Vision contract', () => {
  it('publishes the validated input and all implemented response statuses', async () => {
    const response = await createApp().request('/api/doc', undefined, env);
    const doc = await response.json() as { paths: Record<string, { post: { requestBody: unknown; responses: Record<string, unknown> } }> };
    const operation = doc.paths[path].post;
    expect(operation.requestBody).toMatchObject({ required: true, content: { 'application/json': { schema: {
      required: ['requests'], properties: { requests: { type: 'array', maxItems: 16 } },
    } } } });
    for (const status of ['200', '400', '429', '500', '502']) expect(operation.responses[status]).toBeDefined();
  });
  it('forwards validated input and preserves per-image errors in successful JSON', async () => {
    const payload = { responses: [{ textAnnotations: [{ description: '手順' }] }, { error: { code: 3, message: 'Invalid image' } }] };
    const fetchMock = vi.fn().mockResolvedValue(Response.json(payload)); vi.stubGlobal('fetch', fetchMock);
    const response = await createApp().request(path, request({ requests: [annotation] }), env);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(payload);
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith('https://vision.googleapis.com/v1/images:annotate', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'x-goog-api-key': 'test-only-key' },
      body: JSON.stringify({ requests: [annotation] }),
    });
  });
  it.each([{ requests: Array(17).fill(annotation) }, { requests: [{ image: {} }] }])('rejects invalid bodies before fetching', async body => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock);
    const response = await createApp().request(path, request(body), env);
    expect(response.status).toBe(400);
    expect(appErrorResponseSchema.parse(await response.json()).error.code).toBe('VALIDATION_ERROR');
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it.each([true, false])('returns structured 502 for missing key=%s or upstream rejection', async missingKey => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const fetchMock = vi.fn().mockResolvedValue(new Response('Forbidden', { status: 403 })); vi.stubGlobal('fetch', fetchMock);
    const response = await createApp().request(path, request({ requests: [annotation] }),
      missingKey ? { RATE_LIMIT_ENABLED: 'false' } as Env : env);
    expect(response.status).toBe(502);
    expect(appErrorResponseSchema.parse(await response.json()).error.code).toBe('EXTERNAL_API_ERROR');
    expect(fetchMock).toHaveBeenCalledTimes(missingKey ? 0 : 1);
  });
});

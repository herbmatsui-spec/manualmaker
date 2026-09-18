import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApp } from '../../app';
import type { Env } from '../../lib/types';

const path = '/api/progress/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
afterEach(() => vi.restoreAllMocks());
describe('P9 progress handshake contract (no real WebSocket)', () => {
  it('documents the handshake and forwards non-upgrade requests to the DO', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('Expected WebSocket', { status: 426 }));
    const env = { RATE_LIMIT_ENABLED: 'false', PROGRESS_DO: {
      idFromName: (name: string) => name, get: () => ({ fetch }),
    } } as unknown as Env;
    const app = createApp();
    const docResponse = await app.request('/api/doc', undefined, env);
    const doc = await docResponse.json() as { paths: Record<string, { get: { responses: Record<string, unknown> } }> };
    const responses = doc.paths['/api/progress/{fileId}'].get.responses;
    expect(responses['101']).toBeDefined();
    expect(responses['426']).toMatchObject({ content: { 'text/plain': { schema: { enum: ['Expected WebSocket'] } } } });
    const response = await app.request(path, undefined, env);
    expect(response.status).toBe(426);
    expect(await response.text()).toBe('Expected WebSocket');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(new URL(fetch.mock.calls[0][0].url).pathname).toBe(path);
  });
  it.each([false, true])('documents setup errors, asynchronous=%s', async asynchronous => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const env = { RATE_LIMIT_ENABLED: 'false', PROGRESS_DO: {
      idFromName: () => 'id', get: () => {
        if (!asynchronous) throw new Error('setup failed');
        return { fetch: async () => { throw new Error('forward failed'); } };
      },
    } } as unknown as Env;
    const response = await createApp().request(path, { headers: { Upgrade: 'websocket' } }, env);
    expect(response.status).toBe(500);
    expect(await response.json()).toEqual(asynchronous ? { error: {
      code: 'INTERNAL_ERROR', message: 'Internal server error', requestId: response.headers.get('x-request-id'),
    } } : { error: 'Failed to establish progress connection' });
  });
});

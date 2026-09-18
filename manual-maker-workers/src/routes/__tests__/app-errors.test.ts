import { describe, it, expect, vi, afterEach } from 'vitest';
import { createApp } from '../../app';
import type { Env } from '../../lib/types';

afterEach(() => vi.restoreAllMocks());

describe('Production app error handling', () => {
  it.each([
    ['invalid', 400, 'VALIDATION_ERROR', false],
    ['a'.repeat(32), 404, 'NOT_FOUND', false],
    ['b'.repeat(32), 500, 'INTERNAL_ERROR', true],
  ] as const)('request %s returns %i', async (fileId, status, code, failStorage) => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const get = vi.fn(async () => {
      if (failStorage) throw new Error('private storage detail');
      return null;
    });
    const env = {
      RATE_LIMIT_ENABLED: 'false',
      PROCESSING_KV: { get },
      PROGRESS_DO: {
        idFromName: (name: string) => name,
        get: () => ({ queryProgress: async () => null }),
      },
    } as unknown as Env;
    const response = await createApp().request(`/api/process/${fileId}`, {
      headers: { 'x-request-id': 'app-error-test' },
    }, env);
    expect(response.status).toBe(status);
    expect(response.headers.get('x-request-id')).toBe('app-error-test');
    const body = await response.json();
    expect(body).toMatchObject({ error: { code, requestId: 'app-error-test' } });
    expect(JSON.stringify(body)).not.toContain('private storage detail');
    if (status === 400) expect(get).not.toHaveBeenCalled();
  });
});

import { describe, expect, it, vi } from 'vitest';
import { createApp } from '../../app';
import { deepHealthResponseSchema, failoverResponseSchema } from '../health-contracts';
import type { Env } from '../../lib/types';

describe('P9 health contracts', () => {
  it.each([
    [true, true, 200], [false, true, 503], [true, false, 200],
  ] as const)('primary=%s secondary configured=%s', async (primaryHealthy, secondaryConfigured, status) => {
    const primaryList = vi.fn().mockImplementation(async () => {
      if (!primaryHealthy) throw new Error('Unavailable');
      return { objects: [] };
    });
    const env = {
      RATE_LIMIT_ENABLED: 'false', BUCKET: { list: primaryList },
      PROCESSING_KV: { list: vi.fn().mockResolvedValue({ keys: [] }) },
      ...(secondaryConfigured ? { BUCKET_SECONDARY: { list: vi.fn().mockResolvedValue({ objects: [] }) } } : {}),
    } as unknown as Env;
    const app = createApp();
    const docResponse = await app.request('/api/doc', undefined, env);
    expect(docResponse.status).toBe(200);
    const doc = await docResponse.json() as { paths: Record<string, { get: { responses: Record<string, unknown> } }> };
    expect(doc.paths['/api/health/deep'].get.responses[status]).toMatchObject({ content: { 'application/json': {
      schema: { properties: { status: { enum: [status === 200 ? 'healthy' : 'degraded'] } } },
    } } });
    expect(doc.paths['/api/health/failover-status'].get.responses['200']).toBeDefined();
    const response = await app.request('/api/health/deep', undefined, env);
    expect(response.status).toBe(status);
    expect(response.headers.get('cache-control')).toBe('no-store');
    const deep = deepHealthResponseSchema.parse(await response.json());
    expect(deep.checks.r2).toEqual({ primary: primaryHealthy, secondary: secondaryConfigured, secondaryConfigured });
    const failover = await app.request('/api/health/failover-status', undefined, env);
    expect(failover.status).toBe(200);
    expect(failover.headers.get('cache-control')).toBe('no-store');
    expect(failoverResponseSchema.parse(await failover.json())).toMatchObject({
      primaryR2Healthy: primaryHealthy, failoverRecommended: !primaryHealthy && secondaryConfigured,
      activeR2Bucket: 'primary', failoverMode: 'manual', replicaConsistency: 'unverified',
    });
    expect(primaryList).toHaveBeenCalledTimes(1);
  });
});

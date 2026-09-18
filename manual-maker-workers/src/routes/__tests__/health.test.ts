import { afterEach, describe, it, expect, vi } from 'vitest';
import { Hono } from 'hono';
import { registerHealthRoutes } from '../health';
import { createFailoverManager, FailoverManager } from '../../lib/failover-manager';
import type { AppEnv, Env } from '../../lib/types';

function setup(primary = true, secondary: boolean | undefined = true, kv = true) {
  const probe = (healthy: boolean) => vi.fn(async () => {
    if (!healthy) throw new Error('private backend detail');
    return { objects: [], keys: [], truncated: false, list_complete: true };
  });
  const primaryList = probe(primary);
  const secondaryList = probe(secondary ?? false);
  const kvList = probe(kv);
  const env = { BUCKET: { list: primaryList }, PROCESSING_KV: { list: kvList },
    ...(secondary === undefined ? {} : { BUCKET_SECONDARY: { list: secondaryList } }),
  } as unknown as Env;
  const app = new Hono<AppEnv>(); registerHealthRoutes(app);
  return { app, env, primaryList, secondaryList, kvList };
}
afterEach(() => vi.useRealTimers());

describe('P7 health and failover state', () => {
  it.each([
    [true, true, true, 200], [false, true, true, 503],
    [true, false, true, 503], [false, false, true, 503], [true, true, false, 503],
  ] as const)('independently checks primary=%s secondary=%s kv=%s', async (primary, secondary, kv, status) => {
    const s = setup(primary, secondary, kv);
    const response = await s.app.request('/api/health/deep', undefined, s.env);
    expect(response.status).toBe(status);
    expect(response.headers.get('cache-control')).toBe('no-store');
    const body = await response.json();
    expect(body).toMatchObject({ checks: { r2: { primary, secondary }, kv: { primary: kv } } });
    expect(s.secondaryList).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(body)).not.toContain('private backend detail');
  });
  it('does not mix bindings or state across environments', async () => {
    const a = setup(false, true); const b = setup(true, false);
    const app = a.app;
    await app.request('/api/health/deep', undefined, a.env);
    const response = await app.request('/api/health/failover-status', undefined, b.env);
    expect(await response.json()).toMatchObject({ primaryR2Healthy: true, secondaryR2Healthy: false, activeR2Bucket: 'primary' });
    expect(createFailoverManager(a.env)).not.toBe(createFailoverManager(b.env));
    expect(createFailoverManager(a.env).getStatus().failoverRecommended).toBe(true);
  });
  it('coalesces concurrent checks, caches for 30 seconds and refreshes after expiry', async () => {
    vi.useFakeTimers(); const s = setup();
    const manager = createFailoverManager(s.env);
    expect(manager.getStatus().primaryR2Healthy).toBeNull();
    await Promise.all([manager.refresh(), manager.refresh()]);
    await manager.refresh(); expect(s.primaryList).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(30_001);
    await manager.refresh(); expect(s.primaryList).toHaveBeenCalledTimes(2);
  });
  it('times out hung checks without suppressing other probes or switching storage', async () => {
    vi.useFakeTimers(); const s = setup();
    s.primaryList.mockImplementation(() => new Promise(() => {}));
    const manager = new FailoverManager(s.env, 100);
    const pending = manager.refresh();
    await vi.advanceTimersByTimeAsync(101); await pending;
    expect(manager.getStatus()).toMatchObject({ primaryR2Healthy: false, secondaryR2Healthy: true, failoverRecommended: true });
    expect(manager.getActiveR2Bucket()).toBe(s.env.BUCKET);
    expect(await manager.attemptFailover()).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });
  it('marks an absent secondary explicitly without failing primary-only operation', async () => {
    const s = setup(); delete s.env.BUCKET_SECONDARY;
    const response = await s.app.request('/api/health/deep', undefined, s.env);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ checks: { r2: { secondary: false, secondaryConfigured: false } } });
    expect(s.secondaryList).not.toHaveBeenCalled();
  });
});

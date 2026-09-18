import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CircuitBreaker, CircuitState } from '../circuit-breaker';

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(0); });
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });
const options = { failureThreshold: 1, successThreshold: 1, recoveryTimeoutMs: 1000, timeoutMs: 100 };

describe('P8 step 1 circuit boundaries', () => {
  it.each([true, false])('releases timeout after settled operation, success=%s', async success => {
    const cb = new CircuitBreaker('timer', options);
    const pending = cb.execute(async () => { if (!success) throw new Error('failed'); return 'ok'; });
    if (success) await expect(pending).resolves.toBe('ok');
    else await expect(pending).rejects.toThrow('failed');
    expect(vi.getTimerCount()).toBe(0);
  });
  it('recovers from a failure recorded at timestamp zero', async () => {
    const cb = new CircuitBreaker('epoch', options);
    await expect(cb.execute(async () => { throw new Error('failed'); })).rejects.toThrow('failed');
    await expect(cb.execute(async () => 'ok')).rejects.toMatchObject({ retryAfterSeconds: 1 });
    await vi.advanceTimersByTimeAsync(1000);
    await expect(cb.execute(async () => 'ok')).resolves.toBe('ok');
    expect(cb.getState()).toBe(CircuitState.CLOSED);
  });
  it('counts a timeout once and ignores eventual completion', async () => {
    const cb = new CircuitBreaker('slow', options);
    let resolve!: (value: string) => void;
    const pending = cb.execute(() => new Promise<string>(r => { resolve = r; }));
    const rejected = expect(pending).rejects.toThrow('Operation timeout');
    await vi.advanceTimersByTimeAsync(100);
    await rejected;
    resolve('late');
    await Promise.resolve();
    expect(cb.getMetrics()).toMatchObject({ state: CircuitState.OPEN, failureCount: 1 });
    expect(vi.getTimerCount()).toBe(0);
  });
  it('returns transition fallback without marking the upstream healthy', async () => {
    const onOpen = vi.fn().mockResolvedValue('cached');
    const cb = new CircuitBreaker('fallback', { ...options, onOpen });
    await expect(cb.execute(async () => { throw new Error('failed'); })).resolves.toBe('cached');
    expect(cb.getMetrics()).toMatchObject({ state: CircuitState.OPEN, failureCount: 1 });
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
  it.each(['success', 'failure', 'timeout'] as const)('allows only one recovery probe and releases it after %s', async outcome => {
    const cb = new CircuitBreaker('single-probe', { ...options, successThreshold: 2 });
    await expect(cb.execute(async () => { throw new Error('initial'); })).rejects.toThrow('initial');
    await vi.advanceTimersByTimeAsync(1000);
    let resolve!: (value: string) => void;
    let reject!: (reason: Error) => void;
    const probe = cb.execute(() => new Promise<string>((yes, no) => { resolve = yes; reject = no; }));
    const observed = probe.then(value => ({ value }), error => ({ error }));
    const extra = vi.fn(async () => 'extra');
    const rejected = await Promise.allSettled(Array.from({ length: 8 }, () => cb.execute(extra)));
    expect(rejected.every(result => result.status === 'rejected')).toBe(true);
    expect(extra).not.toHaveBeenCalled();
    expect(cb.getMetrics()).toMatchObject({ state: CircuitState.HALF_OPEN, failureCount: 1, successCount: 0 });
    if (outcome === 'success') resolve('ok');
    else if (outcome === 'failure') reject(new Error('probe failed'));
    else await vi.advanceTimersByTimeAsync(100);
    await observed;
    if (outcome === 'success') {
      expect(cb.getMetrics()).toMatchObject({ state: CircuitState.HALF_OPEN, successCount: 1 });
    } else {
      expect(cb.getState()).toBe(CircuitState.OPEN);
      await vi.advanceTimersByTimeAsync(1000);
    }
    await expect(cb.execute(async () => 'next')).resolves.toBe('next');
    if (outcome === 'success') expect(cb.getState()).toBe(CircuitState.CLOSED);
    else expect(cb.getMetrics()).toMatchObject({ state: CircuitState.HALF_OPEN, successCount: 1 });
    expect(vi.getTimerCount()).toBe(0);
  });
  it('preserves the original failure when transition fallback fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const cb = new CircuitBreaker('fallback-error', { ...options, onOpen: async () => { throw new Error('cache failed'); } });
    await expect(cb.execute(async () => { throw new Error('upstream failed'); })).rejects.toThrow('upstream failed');
    expect(cb.getState()).toBe(CircuitState.OPEN);
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CircuitBreaker, CircuitState } from '../circuit-breaker';

function deferred() {
  let resolve!: (value: string) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<string>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const options = { failureThreshold: 1, successThreshold: 2, recoveryTimeoutMs: 1000 };
beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(0); });
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe('C02 stale operations', () => {
  it.each(['success', 'failure'] as const)('ignores late %s after manual reset', async outcome => {
    const onOpen = vi.fn();
    const cb = new CircuitBreaker('reset', { ...options, onOpen });
    const task = deferred();
    const pending = cb.execute(() => task.promise);
    const observed = pending.catch(error => error);
    cb.reset();
    const snapshot = cb.getMetrics();
    if (outcome === 'success') task.resolve('old');
    else task.reject(new Error('old failure'));
    const result = await observed;
    if (outcome === 'success') expect(result).toBe('old');
    else expect(result).toMatchObject({ message: 'old failure' });
    expect(cb.getMetrics()).toEqual(snapshot);
    expect(onOpen).not.toHaveBeenCalled();
  });

  it.each(['success', 'failure'] as const)('ignores CLOSED-era %s during a recovery probe', async outcome => {
    const cb = new CircuitBreaker('transition', options);
    const old = deferred();
    const observed = cb.execute(() => old.promise).catch(error => error);
    await expect(cb.execute(async () => { throw new Error('trip'); })).rejects.toThrow('trip');
    await vi.advanceTimersByTimeAsync(1000);
    const recovery = deferred();
    const pending = cb.execute(() => recovery.promise);
    const snapshot = cb.getMetrics();
    if (outcome === 'success') old.resolve('stale');
    else old.reject(new Error('stale'));
    await observed;
    expect(cb.getMetrics()).toEqual(snapshot);
    recovery.resolve('healthy');
    await pending;
    expect(cb.getMetrics()).toMatchObject({ state: CircuitState.HALF_OPEN, successCount: 1 });
    await cb.execute(async () => 'healthy');
    expect(cb.getState()).toBe(CircuitState.CLOSED);
  });

  it('does not let an old probe release the new probe slot after reset', async () => {
    const cb = new CircuitBreaker('slot', options);
    const trip = async () => { throw new Error('trip'); };
    await expect(cb.execute(trip)).rejects.toThrow('trip');
    await vi.advanceTimersByTimeAsync(1000);
    const old = deferred();
    const first = cb.execute(() => old.promise);
    cb.reset();
    await expect(cb.execute(trip)).rejects.toThrow('trip');
    await vi.advanceTimersByTimeAsync(1000);
    const current = deferred();
    const second = cb.execute(() => current.promise);
    old.resolve('old');
    await first;
    const extra = vi.fn(async () => 'unexpected');
    await expect(cb.execute(extra)).rejects.toMatchObject({ name: 'CircuitBreakerOpenError' });
    expect(extra).not.toHaveBeenCalled();
    expect(cb.getMetrics().successCount).toBe(0);
    current.resolve('new');
    await second;
    expect(cb.getMetrics()).toMatchObject({ state: CircuitState.HALF_OPEN, successCount: 1 });
  });
});

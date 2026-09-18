import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchWithRetry } from '../http-client';

const url = 'https://example.invalid/test';
const retry = { maxRetries: 1, baseDelayMs: 100, maxDelayMs: 100 };
beforeEach(() => { vi.useFakeTimers(); vi.spyOn(Math, 'random').mockReturnValue(0); });
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('C03 HTTP retry lifecycle', () => {
  it('releases a retryable response before the next attempt', async () => {
    const cancel = vi.fn();
    const unavailable = new Response(new ReadableStream({ cancel }), { status: 503 });
    const ok = Response.json({ ok: true });
    const fetch = vi.fn().mockResolvedValueOnce(unavailable).mockImplementationOnce(async () => {
      expect(cancel).toHaveBeenCalledTimes(1);
      return ok;
    });
    vi.stubGlobal('fetch', fetch);
    const pending = expect(fetchWithRetry(url, {}, retry)).resolves.toBe(ok);
    await vi.advanceTimersByTimeAsync(100);
    await pending;
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('releases the final retryable response and preserves the HTTP error', async () => {
    const cancel = vi.fn().mockRejectedValue(new Error('cleanup failed'));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new ReadableStream({ cancel }), { status: 503 })));
    await expect(fetchWithRetry(url, {}, { maxRetries: 0 })).rejects.toThrow('HTTP 503');
    expect(cancel).toHaveBeenCalledTimes(1);
  });

  it('returns non-retryable responses without consuming their body', async () => {
    const cancel = vi.fn();
    const response = new Response(new ReadableStream({ cancel }), { status: 400 });
    const fetch = vi.fn().mockResolvedValue(response);
    vi.stubGlobal('fetch', fetch);
    expect(await fetchWithRetry(url, {}, retry)).toBe(response);
    expect(response.bodyUsed).toBe(false);
    expect(cancel).not.toHaveBeenCalled();
    expect(fetch).toHaveBeenCalledTimes(1);
    await response.body?.cancel();
  });

  it('does not call fetch when already aborted', async () => {
    const controller = new AbortController();
    const reason = new Error('stop before fetch');
    controller.abort(reason);
    const fetch = vi.fn().mockResolvedValue(Response.json({}));
    vi.stubGlobal('fetch', fetch);
    await expect(fetchWithRetry(url, { signal: controller.signal }, retry)).rejects.toBe(reason);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('aborts the retry delay promptly and removes its listener', async () => {
    const controller = new AbortController();
    const remove = vi.spyOn(controller.signal, 'removeEventListener');
    const fetch = vi.fn().mockRejectedValue(new Error('network'));
    vi.stubGlobal('fetch', fetch);
    const pending = fetchWithRetry(url, { signal: controller.signal }, retry);
    const observed = pending.catch(error => error);
    await vi.advanceTimersByTimeAsync(0);
    expect(vi.getTimerCount()).toBe(1);
    const reason = new Error('stop during delay');
    controller.abort(reason);
    // Flush a microtask turn without advancing the retry timer.
    await vi.advanceTimersByTimeAsync(0);
    expect(vi.getTimerCount()).toBe(0);
    expect(await observed).toBe(reason);
    expect(remove).toHaveBeenCalledWith('abort', expect.any(Function));
    await vi.advanceTimersByTimeAsync(1000);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('forwards the signal and never retries an aborted fetch', async () => {
    const controller = new AbortController();
    const fetch = vi.fn((_url: string, options: RequestInit) => new Promise<Response>((_resolve, reject) => {
      expect(options.signal).toBe(controller.signal);
      options.signal?.addEventListener('abort', () => reject(options.signal?.reason), { once: true });
    }));
    vi.stubGlobal('fetch', fetch);
    const observed = fetchWithRetry(url, { signal: controller.signal }, retry).catch(error => error);
    const reason = new Error('stop fetching');
    controller.abort(reason);
    await vi.advanceTimersByTimeAsync(0);
    expect(vi.getTimerCount()).toBe(0);
    expect(await observed).toBe(reason);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

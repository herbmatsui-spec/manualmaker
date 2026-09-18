interface RetryOptions {
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  retryableStatuses?: number[];
}

function waitForRetry(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    signal?.throwIfAborted();
    const cleanup = () => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
    };
    const onAbort = () => {
      cleanup();
      reject(signal?.reason);
    };
    const timer = setTimeout(() => {
      cleanup();
      resolve();
    }, ms);
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

export async function fetchWithRetry(
  url: string,
  options: RequestInit,
  retryOptions: RetryOptions = {}
): Promise<Response> {
  const {
    maxRetries = 3,
    baseDelayMs = 500,
    maxDelayMs = 5000,
    retryableStatuses = [429, 500, 502, 503, 504]
  } = retryOptions;

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    options.signal?.throwIfAborted();
    try {
      const response = await fetch(url, options);
      if (!retryableStatuses.includes(response.status)) {
        return response;
      }
      lastError = new Error(`HTTP ${response.status}`);
      // Cleanup failure must not replace the provider's HTTP error.
      await response.body?.cancel().catch(() => {});
    } catch (err) {
      options.signal?.throwIfAborted();
      lastError = err as Error;
    }

    if (attempt < maxRetries) {
      const delay = Math.min(baseDelayMs * 2 ** attempt, maxDelayMs);
      await waitForRetry(delay + Math.random() * 100, options.signal);
    }
  }

  throw lastError;
}
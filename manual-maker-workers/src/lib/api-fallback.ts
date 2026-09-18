import { CircuitBreaker, CircuitBreakerOpenError, CircuitState } from './circuit-breaker';
import type { FallbackCache } from './fallback-cache';

/** Opaque, versioned key: never put credentials or request text into KV key names. */
export async function apiCacheKey(service: string, credential: string, operation: string, request: unknown): Promise<string> {
  const input = JSON.stringify([credential, operation, request]);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  return `${service}:v2:${Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')}`;
}

/** Fallback is request-scoped, not a mutable callback shared by concurrent requests. */
export async function executeWithApiFallback<T>(
  breaker: CircuitBreaker,
  cache: FallbackCache,
  key: string,
  operation: (signal: AbortSignal) => Promise<T>,
): Promise<T> {
  let result: T;
  try {
    result = await breaker.execute(operation);
  } catch (error) {
    if (error instanceof CircuitBreakerOpenError || breaker.getState() === CircuitState.OPEN) {
      try {
        const cached = await cache.getCachedResult<T>(key);
        if (cached !== null) return cached;
      } catch {
        // Preserve the upstream/open-circuit error, never expose cache contents.
        console.warn('External API fallback cache read failed');
      }
    }
    throw error;
  }
  try {
    await cache.cacheResult(key, result, 300);
  } catch {
    console.warn('External API fallback cache write failed');
  }
  return result;
}

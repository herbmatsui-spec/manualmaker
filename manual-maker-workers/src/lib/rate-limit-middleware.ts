import { Context, Next } from 'hono';
import { RateLimitError } from '../lib/errors';
import {
  createRateLimiter,
  rateLimitConfigs,
  type RateLimitConfig,
  type RateLimitResult,
  type RateLimitExceeded,
} from './rate-limiter';

export function rateLimit(
  configKey: keyof typeof rateLimitConfigs,
  opts?: { keyExtractor?: (c: Context) => string; skipFailed?: boolean }
) {
  const { keyExtractor, skipFailed = true } = opts ?? {};

  return async (c: Context, next: Next) => {
    if (c.env.RATE_LIMIT_ENABLED === 'false') {
      return await next();
    }

    try {
      const config = rateLimitConfigs[configKey];
      const limiter = createRateLimiter(c.env, config);

      const getKey = keyExtractor ?? ((c: Context) => {
        return c.req.header('cf-connecting-ip') || 'unknown';
      });

const key = getKey(c);
       const result = await limiter.consume(key);
       console.log('Consume result:', result, 'key:', key);

       if (!result.allowed) {
        const headers = new Headers();
        headers.set('Retry-After', String(result.retryAfter));
        headers.set('RateLimit-Limit', String(config.maxRequests));
        headers.set('RateLimit-Remaining', '0');
        headers.set('RateLimit-Reset', String(result.resetAt));
        headers.forEach((value, key) => {
          c.res.headers.set(key, value);
        });
        return c.json(
          { error: 'Too many requests', retryAfter: result.retryAfter },
          429
        );
      }

      await next();

      // 成功時にヘッダーを追加
      const headers = new Headers();
      headers.set('RateLimit-Limit', String(config.maxRequests));
      headers.set(
        'RateLimit-Remaining',
        String(Math.max(0, config.maxRequests - result.count))
      );
      headers.set('RateLimit-Reset', String(result.resetAt));
      headers.forEach((value, key) => {
        c.res.headers.set(key, value);
      });
    } catch (err) {
      if (err instanceof RateLimitError) {
        const details = err.details as { retryAfter?: number } | undefined;
        return c.json(
          { error: 'Too many requests', retryAfter: details?.retryAfter },
          429
        );
      }

      if (!skipFailed) {
        throw err;
      }

      await next();
    }
  };
}

// 特定用途のミドルウェアヘルパー（ファクトリ関数）
export function rateLimitUpload(
  opts?: { keyExtractor?: (c: Context) => string }
) {
  return rateLimit('upload', {
    keyExtractor:
      opts?.keyExtractor ?? ((c: Context) => c.req.header('cf-connecting-ip') || 'unknown'),
  });
}

export function rateLimitGeminiProxy(
  opts?: { keyExtractor?: (c: Context) => string }
) {
  return rateLimit('geminiProxy', {
    keyExtractor:
      opts?.keyExtractor ?? ((c: Context) => c.req.header('cf-connecting-ip') || 'unknown'),
  });
}

export function rateLimitVisionProxy(
  opts?: { keyExtractor?: (c: Context) => string }
) {
  return rateLimit('visionProxy', {
    keyExtractor:
      opts?.keyExtractor ?? ((c: Context) => c.req.header('cf-connecting-ip') || 'unknown'),
  });
}

export function rateLimitProgressUpdate(
  opts?: { keyExtractor?: (c: Context) => string }
) {
  return rateLimit('progressUpdate', {
    keyExtractor:
      opts?.keyExtractor ??
      ((c: Context) => {
        const fileId = c.req.param('fileId');
        return fileId || c.req.header('cf-connecting-ip') || 'unknown';
      }),
  });
}

export function rateLimitIPGeneral(
  opts?: { keyExtractor?: (c: Context) => string }
) {
  return rateLimit('ipGeneral', {
    keyExtractor: opts?.keyExtractor ?? ((c: Context) => c.req.header('cf-connecting-ip') || 'unknown'),
  });
}
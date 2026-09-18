import { Context, Next } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import { AppError } from './errors';

export function correlationId() {
  return async (c: Context, next: Next) => {
    const requestId = c.req.header('x-request-id') || crypto.randomUUID();
    c.set('requestId', requestId);
    c.header('x-request-id', requestId);
    await next();
  };
}

/** Hono catches route exceptions before they can reach middleware's catch block. */
export function handleAppError(err: unknown, c: Context) {
  const requestId = c.get('requestId') || 'unknown';
  console.error(`[${requestId}] Unhandled error:`, err);
  if (err instanceof AppError) {
    const status = err.statusCode >= 400 && err.statusCode <= 599
      ? err.statusCode as ContentfulStatusCode : 500;
    return c.json(
      { error: { code: err.code, message: err.message, requestId, details: err.details } },
      status,
    );
  }
  return c.json(
    { error: { code: 'INTERNAL_ERROR', message: 'Internal server error', requestId } },
    500,
  );
}

export function errorHandler() {
  return async (c: Context, next: Next) => {
    try {
      await next();
    } catch (err) {
      return handleAppError(err, c);
    }
  };
}
import { Context, Next } from 'hono';

interface BodyLimitOptions {
  maxSize: number; // bytes
  errorMessage?: string;
}

export function bodyLimit({ maxSize, errorMessage = 'Request body too large' }: BodyLimitOptions) {
  return async (c: Context, next: Next) => {
    const contentLength = c.req.header('content-length');
    if (contentLength && parseInt(contentLength, 10) > maxSize) {
      return c.json({ error: errorMessage, maxSize }, 413);
    }
    await next();
  };
}
import type { Context, Next } from 'hono';
import { OpenAPIHono } from '@hono/zod-openapi';
import { cors } from 'hono/cors';
import { etag } from 'hono/etag';
import { logger } from 'hono/logger';
import type { AppEnv } from './lib/types';
import { rateLimitIPGeneral } from './lib/rate-limit-middleware';
import { correlationId, handleAppError } from './lib/middleware';
import { registerRoutes } from './routes';

const rateLimitIPGeneralExcept = async (c: Context<AppEnv>, next: Next) => {
  const excludedPaths = ['/api/health', '/api/metrics'];
  if (excludedPaths.some(path => c.req.path.startsWith(path))) return next();
  await rateLimitIPGeneral()(c, next);
};

export function createApp() {
  const app = new OpenAPIHono<AppEnv>();
  app.onError(handleAppError);
  app.use('*', correlationId());
  app.use('*', cors());
  app.use('*', etag());
  app.use('*', logger());
  app.use('*', rateLimitIPGeneralExcept);
  registerRoutes(app);
  app.notFound(c => c.json({ error: 'Not found' }, 404));
  return app;
}

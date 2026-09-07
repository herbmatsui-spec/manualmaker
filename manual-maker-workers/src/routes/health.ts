/**
 * Health check routes
 */
import { Hono } from 'hono';
import type { Env, HealthResponse } from '../lib/types';

export function registerHealthRoutes(app: Hono<{ Bindings: Env }>) {
  app.get('/api/health', (c) => {
    const response: HealthResponse = {
      status: 'ok',
      version: '2.0.0',
      processorType: 'cloudflare-workers'
    };
    return c.json(response);
  });
}

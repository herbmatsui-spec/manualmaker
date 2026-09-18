/**
 * Config routes
 */
import { Hono } from 'hono';
import type { AppEnv, ConfigResponse } from '../lib/types';
import { getConfig } from '../lib/config-cache';

export function registerConfigRoutes(app: Hono<AppEnv>) {
  app.get('/api/config', (c) => {
    const config = getConfig(c.env);
    return c.json(config);
  });
}

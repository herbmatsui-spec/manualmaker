import { describe, it, expect } from 'vitest';
import { OpenAPIHono } from '@hono/zod-openapi';
import type { AppEnv } from '../../lib/types';
import { registerHealthRoutes } from '../health';
import { registerOpenAPIRoutes } from '../openapi';

// No entry point, other application routes, or cloud service mocks.
describe('Isolated health OpenAPI smoke test', () => {
  it('documents the real health response', async () => {
    const app = new OpenAPIHono<AppEnv>();
    registerHealthRoutes(app);
    registerOpenAPIRoutes(app);

    const health = await app.request('/api/health');
    expect(health.status).toBe(200);
    expect(await health.json()).toEqual({
      status: 'ok', version: '2.0.0', processorType: 'cloudflare-workers',
    });

    const document = await app.request('/api/doc');
    expect(document.status).toBe(200);
    expect(await document.json()).toMatchObject({
      openapi: '3.1.0',
      info: { title: 'Manual Maker API', version: '2.0.0' },
      paths: {
        '/api/health': {
          get: {
            responses: {
              '200': {
                content: {
                  'application/json': {
                    schema: {
                      type: 'object',
                      required: ['status', 'version', 'processorType'],
                      properties: {
                        status: { type: 'string', enum: ['ok'] },
                        version: { type: 'string', enum: ['2.0.0'] },
                        processorType: { type: 'string', enum: ['cloudflare-workers'] },
                      },
                    },
                  },
                },
              },
            },
          },
        },
      },
    });
  });
});

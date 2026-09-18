import { describe, expect, it } from 'vitest';
import { createApp } from '../../app';
import type { Env } from '../../lib/types';

type Operation = {
  responses: Record<string, { description?: string }>;
  parameters?: Array<{ name: string; in: string; required?: boolean }>;
  operationId?: string;
};

describe('P9 production route inventory', () => {
  it('documents exactly the registered business operations with valid path parameters', async () => {
    const app = createApp();
    const response = await app.request('/api/doc', undefined, { RATE_LIMIT_ENABLED: 'false' } as Env);
    expect(response.status).toBe(200);
    const doc = await response.json() as { openapi: string; paths: Record<string, Record<string, Operation>> };
    expect(doc.openapi).toBe('3.1.0');
    const methods = new Set(['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']);
    // Hono stores middleware separately and repeats a route for each route middleware.
    // /api/doc describes the API itself, not a business operation.
    const actual = [...new Set(app.routes
      .filter(route => methods.has(route.method) && route.path !== '/api/doc')
      .map(route => `${route.method} ${route.path.replace(/:([\w]+)/g, '{$1}')}`))].sort();
    const documented: string[] = [];
    const ids: string[] = [];
    for (const [path, item] of Object.entries(doc.paths)) {
      for (const [method, operation] of Object.entries(item)) {
        if (!methods.has(method.toUpperCase())) continue;
        documented.push(`${method.toUpperCase()} ${path}`);
        expect(Object.keys(operation.responses).length).toBeGreaterThan(0);
        for (const [status, result] of Object.entries(operation.responses)) {
          expect(status).toMatch(/^[1-5]\d\d$|^default$/);
          expect(typeof result.description).toBe('string');
        }
        const placeholders = [...path.matchAll(/\{([^}]+)\}/g)].map(match => match[1]).sort();
        const params = (operation.parameters ?? []).filter(parameter => parameter.in === 'path');
        expect(params.map(parameter => parameter.name).sort(), `${method} ${path}`).toEqual(placeholders);
        expect(params.every(parameter => parameter.required === true)).toBe(true);
        if (operation.operationId) ids.push(operation.operationId);
      }
    }
    expect(documented.sort()).toEqual(actual);
    expect(new Set(ids).size).toBe(ids.length);
    expect(actual.length).toBeGreaterThan(20);
  });
});

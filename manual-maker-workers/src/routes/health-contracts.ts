import { z, type OpenAPIHono } from '@hono/zod-openapi';
import type { AppEnv } from '../lib/types';

export const deepHealthResponseSchema = z.object({
  status: z.enum(['healthy', 'degraded']),
  timestamp: z.string().datetime(),
  checkedAt: z.string().datetime(),
  probeType: z.literal('read-only availability'),
  checks: z.object({
    r2: z.object({ primary: z.boolean(), secondary: z.boolean(), secondaryConfigured: z.boolean() }),
    kv: z.object({ primary: z.boolean() }),
  }),
  replicaConsistency: z.literal('unverified'),
}).strict();

export const failoverResponseSchema = z.object({
  timestamp: z.string().datetime(),
  primaryR2Healthy: z.boolean(),
  secondaryR2Healthy: z.boolean(),
  secondaryConfigured: z.boolean(),
  primaryKVHealthy: z.boolean(),
  lastCheckedAt: z.string().datetime(),
  failoverInProgress: z.literal(false),
  failoverMode: z.literal('manual'),
  failoverRecommended: z.boolean(),
  replicaConsistency: z.literal('unverified'),
  activeR2Bucket: z.literal('primary'),
}).strict();

export function registerHealthContracts(app: OpenAPIHono<AppEnv>) {
  const headers = { 'Cache-Control': { schema: { type: 'string' as const, enum: ['no-store'] } } };
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/health/deep', operationId: 'getDeepHealth',
    description: 'Read-only R2/KV availability, cached for 30 seconds per environment instance. Does not verify replica consistency or write access.',
    responses: {
      200: { description: 'Configured storage is available', headers, content: {
        'application/json': { schema: deepHealthResponseSchema.extend({ status: z.literal('healthy') }) },
      } },
      503: { description: 'At least one configured storage probe failed', headers, content: {
        'application/json': { schema: deepHealthResponseSchema.extend({ status: z.literal('degraded') }) },
      } },
    },
  });
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/health/failover-status', operationId: 'getFailoverStatus',
    description: 'Always returns 200 after probing; inspect health fields. A recommendation does not switch bindings. Operator approval and consistency verification are required.',
    responses: {
      200: { description: 'Manual failover assessment', headers, content: {
        'application/json': { schema: failoverResponseSchema },
      } },
    },
  });
}

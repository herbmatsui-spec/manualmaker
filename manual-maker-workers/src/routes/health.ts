import { Hono } from 'hono';
import { validate } from '../lib/validation';
import { openapiConfigQuery } from '../lib/openapi-schemas';
import { FailoverManager, createFailoverManager } from '../lib/failover-manager';
import type { AppEnv } from '../lib/types';

export function registerHealthRoutes(app: Hono<AppEnv>) {
  app.get('/api/health', validate({ query: openapiConfigQuery }), c => c.json({
    status: 'ok', version: '2.0.0', processorType: 'cloudflare-workers',
  }));

  app.get('/api/health/deep', async c => {
    const manager = createFailoverManager(c.env);
    await manager.refresh();
    const state = manager.getStatus();
    const healthy = state.primaryR2Healthy && state.primaryKVHealthy &&
      (!state.secondaryConfigured || state.secondaryR2Healthy);
    c.header('Cache-Control', 'no-store');
    return c.json({
      status: healthy ? 'healthy' : 'degraded',
      timestamp: new Date().toISOString(),
      checkedAt: state.lastCheckedAt,
      probeType: 'read-only availability',
      checks: {
        r2: { primary: state.primaryR2Healthy, secondary: state.secondaryR2Healthy,
          secondaryConfigured: state.secondaryConfigured },
        kv: { primary: state.primaryKVHealthy },
      },
      replicaConsistency: state.replicaConsistency,
    }, healthy ? 200 : 503);
  });

  app.get('/api/health/failover-status', async c => {
    const manager = createFailoverManager(c.env);
    await manager.refresh();
    c.header('Cache-Control', 'no-store');
    return c.json({
      timestamp: new Date().toISOString(), ...manager.getStatus(),
      activeR2Bucket: 'primary',
    });
  });
}

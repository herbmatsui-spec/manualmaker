import { Hono } from 'hono';
import { createGeminiApi } from '../lib/external-api';
import { createVisionApi } from '../lib/external-api';
import type { AppEnv } from '../lib/types';
import type { ProgressMetrics } from '../lib/progress-metrics';
import { rateLimitConfigs } from '../lib/rate-limiter';

let geminiApiInstance: ReturnType<typeof createGeminiApi> | null = null;
let visionApiInstance: ReturnType<typeof createVisionApi> | null = null;

export function setApiInstances(geminiApi: ReturnType<typeof createGeminiApi>, visionApi: ReturnType<typeof createVisionApi>) {
  geminiApiInstance = geminiApi;
  visionApiInstance = visionApi;
}

export function registerMetricsRoutes(app: Hono<AppEnv>) {
  app.get('/api/metrics/circuit-breakers', async (c) => {
    const result: Record<string, any> = {
      timestamp: new Date().toISOString(),
      gemini: {},
      vision: {}
    };
    
    if (geminiApiInstance && typeof geminiApiInstance.getCircuitMetrics === 'function') {
      result.gemini = geminiApiInstance.getCircuitMetrics();
    }
    
    if (visionApiInstance && typeof visionApiInstance.getCircuitMetrics === 'function') {
      result.vision = visionApiInstance.getCircuitMetrics();
    }
    
    return c.json(result);
  });

app.get('/api/metrics/rate-limit', async (c) => {
       const requestId = c.get('requestId') || 'unknown';
       try {
         const now = Date.now();
         const result = {
           timestamp: new Date().toISOString(),
            rateLimitMetrics: {} as Record<string, {
              windowMs: number;
              maxRequests: number;
              currentWindowIndex: number;
              totalRequests: number;
              blockedRequests: number;
              uniqueIdentifiers: number;
            }>
         };

         for (const [configKey, config] of Object.entries(rateLimitConfigs)) {
           const windowDuration = config.windowMs / 1000;
           const windowIndex = Math.floor(now / windowDuration);
           const prefix = `${config.keyPrefix}:`;
           
           const listResult = await c.env.PROCESSING_KV.list({ prefix });
           let totalRequests = 0;
           let blockedRequests = 0;
           let uniqueIdentifiers = new Set();
           
           for (const item of listResult.keys) {
             // Extract the key and window index from the item name
             // Format: {keyPrefix}:{identifier}:{windowIndex} or {keyPrefix}:{identifier}:{windowIndex}:blocked
             const parts = item.name.split(':');
             if (parts.length < 3) continue;
             const itemKeyPrefix = parts.slice(0, -2).join(':');
             if (itemKeyPrefix !== config.keyPrefix) continue;
             const identifier = parts.slice(-3, -2)[0];
             const itemWindowIndex = parseInt(parts.slice(-2, -1)[0], 10);
             const isBlocked = parts.length === 5 && parts[4] === 'blocked';
             
             // Only consider the current window
             if (itemWindowIndex !== windowIndex) continue;
             
             uniqueIdentifiers.add(identifier);
             
             const value = await c.env.PROCESSING_KV.get(item.name);
             const count = value ? parseInt(value, 10) : 0;
             
             if (isBlocked) {
               blockedRequests += count;
             } else {
               totalRequests += count;
             }
           }
           
           result.rateLimitMetrics[configKey] = {
             windowMs: config.windowMs,
             maxRequests: config.maxRequests,
             currentWindowIndex: windowIndex,
             totalRequests,
             blockedRequests,
             uniqueIdentifiers: uniqueIdentifiers.size,
             // We can optionally include identifier details, but skip for brevity
           };
         }

         return c.json(result);
       } catch (error) {
         console.error(`[${requestId}] Rate limit metrics error:`, error);
         return c.json({ error: 'Failed to get rate limit metrics' }, 500);
       }
     });

  app.post('/api/system/reset-circuit-breakers', async (c) => {
    if (geminiApiInstance && typeof geminiApiInstance.resetCircuitBreaker === 'function') {
      geminiApiInstance.resetCircuitBreaker();
    }
    
    if (visionApiInstance && typeof visionApiInstance.resetCircuitBreaker === 'function') {
      visionApiInstance.resetCircuitBreaker();
    }
    
    return c.json({
      success: true,
      message: 'Circuit breakers reset',
      timestamp: new Date().toISOString()
    });
  });

  // Progress DO metrics aggregation
  app.get('/api/metrics/progress', async (c) => {
    const requestId = c.get('requestId') || 'unknown';
    try {
      const prefix = 'progress-metrics:';
      let cursor: string | undefined;
      let activeConnections = 0;
      let totalUpdates = 0;
      let broadcastBytes = 0;
      let count = 0;
      do {
        const listResult: KVNamespaceListResult<unknown> = await c.env.PROCESSING_KV.list({
          prefix,
          cursor,
          limit: 1000
        });
        for (const item of listResult.keys) {
          const value = await c.env.PROCESSING_KV.get<Partial<ProgressMetrics>>(item.name, 'json');
          if (value && typeof value === 'object') {
            activeConnections += value.activeConnections ?? 0;
            totalUpdates += value.totalUpdates ?? 0;
            broadcastBytes += value.broadcastBytes ?? 0;
            count++;
          }
        }
        cursor = listResult.list_complete ? undefined : listResult.cursor;
      } while (cursor);

      return c.json({
        timestamp: new Date().toISOString(),
        activeConnections,
        totalUpdates,
        broadcastBytes,
        sources: count
      });
    } catch (error) {
      console.error(`[${requestId}] Failed to aggregate progress metrics:`, error);
      return c.json({ error: 'Failed to get progress metrics' }, 500);
    }
  });
}
/**
 * Gemini API proxy routes
 * Proxies requests to Google Gemini API to avoid exposing API keys client-side
 */
import { Hono } from 'hono';
import type { AppEnv } from '../lib/types';
import { validate, getValidatedBody, getValidatedParams } from '../lib/validation';
import { bodyLimit } from '../lib/body-limit';
import { openapiGeminiProxyParams, openapiGeminiProxyBody } from '../lib/openapi-schemas';
import { ExternalAPIError } from '../lib/errors';
import { z } from 'zod';
import { rateLimitGeminiProxy } from '../lib/rate-limit-middleware';
import { getGeminiApi } from '../lib/external-api';

export function registerGeminiRoutes(app: Hono<AppEnv>) {
  /**
   * POST /api/gemini/:model/:method
   * e.g. /api/gemini/gemini-1.5-flash/generateContent
   */
  app.post('/api/gemini/:model/:method',
    rateLimitGeminiProxy(),
    bodyLimit({ maxSize: 10 * 1024 * 1024 }), // 10MB as per C2 plan
    validate({ params: openapiGeminiProxyParams, body: openapiGeminiProxyBody }),
    async (c) => {
      const { model, method } = getValidatedParams<{ model: string; method: string }>(c);
      const body = getValidatedBody<Record<string, unknown>>(c);

      const result = await getGeminiApi(c.env).callModel(model, method, body);
      return c.json(result);
    }
  );

  /**
   * GET /api/gemini/models - list available models
   */
  app.get('/api/gemini/models',
    async (c) => {
      const result = await getGeminiApi(c.env).listModels();
      return c.json(result);
    }
  );
}
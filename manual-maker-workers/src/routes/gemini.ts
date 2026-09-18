/**
 * Gemini API proxy routes
 * Proxies requests to Google Gemini API to avoid exposing API keys client-side
 */
import { Hono } from 'hono';
import type { AppEnv } from '../lib/types';
import { validate, getValidatedBody, getValidatedParams } from '../lib/validation';
import { bodyLimit } from '../lib/body-limit';
import { geminiProxyParams, geminiProxyBody } from '../lib/schemas';
import { fetchWithRetry } from '../lib/http-client';
import { ExternalAPIError, ValidationError } from '../lib/errors';
import { z } from 'zod';
import { rateLimitGeminiProxy } from '../lib/rate-limit-middleware';

const GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta';

export function registerGeminiRoutes(app: Hono<AppEnv>) {
  /**
   * POST /api/gemini/:model/:method
   * e.g. /api/gemini/gemini-1.5-flash/generateContent
   */
  app.post('/api/gemini/:model/:method',
    rateLimitGeminiProxy(),
    bodyLimit({ maxSize: 10 * 1024 * 1024 }), // 10MB as per C2 plan
    validate({ params: geminiProxyParams, body: geminiProxyBody }),
    async (c) => {
      const { model, method } = getValidatedParams<{ model: string; method: string }>(c);
      const body = getValidatedBody<Record<string, unknown>>(c);

      const apiKey = c.env.GEMINI_API_KEY;
      if (!apiKey) {
        throw new ExternalAPIError('gemini', 'GEMINI_API_KEY not configured', undefined, 503);
      }

      const url = `${GEMINI_API_BASE}/models/${model}:${method}`;
      const response = await fetchWithRetry(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-goog-api-key': apiKey
        },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new ExternalAPIError('gemini', `Gemini API error: ${errorText.slice(0, 500)}`, response.status);
      }

      const result = await response.json();
      return c.json(result);
    }
  );

  /**
   * GET /api/gemini/models - list available models
   */
  app.get('/api/gemini/models',
    validate({ query: z.object({}) }),
    async (c) => {
      const apiKey = c.env.GEMINI_API_KEY;
      if (!apiKey) {
        throw new ExternalAPIError('gemini', 'GEMINI_API_KEY not configured', undefined, 503);
      }

      const response = await fetchWithRetry(`${GEMINI_API_BASE}/models`, {
        headers: { 'x-goog-api-key': apiKey }
      });

      if (!response.ok) {
        throw new ExternalAPIError('gemini', 'Gemini API error', response.status);
      }

      const result = await response.json();
      return c.json(result);
    }
  );
}
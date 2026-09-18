/**
 * Google Cloud Vision API proxy routes
 * For handwritten OCR - image annotation
 */
import { Hono } from 'hono';
import type { AppEnv } from '../lib/types';
import { fetchWithRetry } from '../lib/http-client';
import { ExternalAPIError, ValidationError } from '../lib/errors';
import { validate, getValidatedBody } from '../lib/validation';
import { z } from 'zod';
import { openapiVisionProxyBody } from '../lib/openapi-schemas';
import { rateLimitVisionProxy } from '../lib/rate-limit-middleware';

const VISION_API_BASE = 'https://vision.googleapis.com/v1';

export function registerVisionRoutes(app: Hono<AppEnv>) {
  /**
   * POST /api/vision/annotate
   * Body: { requests: [{ image: { content: base64 }, features: [...] }] }
   */
  app.post('/api/vision/annotate',
    rateLimitVisionProxy(),
    bodyLimit({ maxSize: 10 * 1024 * 1024 }), // 10MB as per C2 plan
    validate({ body: openapiVisionProxyBody }),
    async (c) => {
      const apiKey = c.env.GOOGLE_API_KEY;
      if (!apiKey) {
        throw new ExternalAPIError('vision', 'GOOGLE_API_KEY not configured', undefined, 503);
      }

      const body = getValidatedBody<{ requests: Array<{ image: { content: string }; features: Array<{ type: string; maxResults?: number }> }> }>(c);

      const response = await fetchWithRetry(`${VISION_API_BASE}/images:annotate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-goog-api-key': apiKey
        },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new ExternalAPIError('vision', `Vision API error: ${errorText.slice(0, 500)}`, response.status);
      }

      const result = await response.json();
      return c.json(result);
    }
  );
}
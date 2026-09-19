/**
 * Google Cloud Vision API proxy routes
 * For handwritten OCR - image annotation
 */
import { Hono } from 'hono';
import type { AppEnv } from '../lib/types';
import { validate, getValidatedBody } from '../lib/validation';
import { bodyLimit } from '../lib/body-limit';
import { z } from 'zod';
import { openapiVisionProxyBody } from '../lib/openapi-schemas';
import { rateLimitVisionProxy } from '../lib/rate-limit-middleware';
import { visionApi } from '../index';

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
      const body = getValidatedBody<{ requests: Array<{ image: { content: string }; features: Array<{ type: string; maxResults?: number }> }> }>(c);

      const result = await visionApi.annotateImage(body);
      return c.json(result);
    }
  );
}
/**
 * Google Cloud Vision API proxy routes
 * For handwritten OCR - image annotation
 */
import { Hono } from 'hono';
import type { Env } from '../lib/types';

const VISION_API_BASE = 'https://vision.googleapis.com/v1';

export function registerVisionRoutes(app: Hono<{ Bindings: Env }>) {
  /**
   * POST /api/vision/annotate
   * Body: { requests: [{ image: { content: base64 }, features: [...] }] }
   */
  app.post('/api/vision/annotate', async (c) => {
    try {
      const apiKey = c.env.GOOGLE_API_KEY;
      if (!apiKey) {
        return c.json({ error: 'GOOGLE_API_KEY not configured' }, 503);
      }

      const body = await c.req.json();

      // Basic validation
      if (!body.requests || !Array.isArray(body.requests)) {
        return c.json({ error: 'Invalid request format: requests array required' }, 400);
      }

      if (body.requests.length > 16) {
        return c.json({ error: 'Too many requests (max 16 per batch)' }, 400);
      }

      const response = await fetch(`${VISION_API_BASE}/images:annotate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-goog-api-key': apiKey
        },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Vision API error (${response.status}):`, errorText.slice(0, 500));
        return c.json(
          { error: 'Vision API error', status: response.status },
          response.status === 429 ? 429 : 502
        );
      }

      const result = await response.json();
      return c.json(result);
    } catch (error) {
      console.error('Vision proxy error:', error);
      return c.json({ error: 'Proxy failed' }, 500);
    }
  });
}

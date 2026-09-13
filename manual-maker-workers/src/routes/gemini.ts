/**
 * Gemini API proxy routes
 * Proxies requests to Google Gemini API to avoid exposing API keys client-side
 */
import { Hono } from 'hono';
import type { Env } from '../lib/types';

const GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta';

export function registerGeminiRoutes(app: Hono<{ Bindings: Env }>) {
  /**
   * POST /api/gemini/:model/:method
   * e.g. /api/gemini/gemini-1.5-flash/generateContent
   */
  app.post('/api/gemini/:model/:method', async (c) => {
    try {
      const model = c.req.param('model');
      const method = c.req.param('method');

      const apiKey = c.env.GEMINI_API_KEY;
      if (!apiKey) {
        return c.json({ error: 'GEMINI_API_KEY not configured' }, 503);
      }

      // Validate model name to prevent SSRF
      if (!/^[a-z0-9.\-]+$/i.test(model)) {
        return c.json({ error: 'Invalid model name' }, 400);
      }

      // Validate method
      const allowedMethods = ['generateContent', 'streamGenerateContent', 'countTokens'];
      if (!allowedMethods.includes(method)) {
        return c.json({ error: 'Invalid method' }, 400);
      }

      const body = await c.req.json();

      const url = `${GEMINI_API_BASE}/models/${model}:${method}`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-goog-api-key': apiKey
        },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Gemini API error (${response.status}):`, errorText.slice(0, 500));
        return c.json(
          { error: 'Gemini API error', status: response.status },
          response.status === 429 ? 429 : 502
        );
      }

      const result = await response.json();
      return c.json(result);
    } catch (error) {
      console.error('Gemini proxy error:', error);
      return c.json({ error: 'Proxy failed' }, 500);
    }
  });

  /**
   * GET /api/gemini/models - list available models
   */
  app.get('/api/gemini/models', async (c) => {
    try {
      const apiKey = c.env.GEMINI_API_KEY;
      if (!apiKey) {
        return c.json({ error: 'GEMINI_API_KEY not configured' }, 503);
      }

      const response = await fetch(`${GEMINI_API_BASE}/models`, {
        headers: { 'x-goog-api-key': apiKey }
      });

      if (!response.ok) {
        return c.json({ error: 'Gemini API error', status: response.status }, 502);
      }

      const result = await response.json();
      return c.json(result);
    } catch (error) {
      console.error('Gemini list models error:', error);
      return c.json({ error: 'Proxy failed' }, 500);
    }
  });
}

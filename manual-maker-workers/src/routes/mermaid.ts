/**
 * Mermaid routes - metadata only (rendering/validation happens client-side)
 */
import { Hono } from 'hono';
import type { Env } from '../lib/types';
import { validateFileId } from '../lib/utils';

export function registerMermaidRoutes(app: Hono<{ Bindings: Env }>) {
  /**
   * POST /api/mermaid/save/:fileId
   * Save edited mermaid diagram source
   */
  app.post('/api/mermaid/save/:fileId', async (c) => {
    try {
      const fileId = c.req.param('fileId');
      if (!validateFileId(fileId)) {
        return c.json({ error: 'Invalid fileId format' }, 400);
      }

      const body = await c.req.json();
      if (typeof body.mermaid !== 'string' || body.mermaid.length === 0) {
        return c.json({ error: 'mermaid field is required' }, 400);
      }

      if (body.mermaid.length > 512 * 1024) {
        return c.json({ error: 'Mermaid source too large (max 512KB)' }, 413);
      }

      const key = `results/${fileId}/diagram.mmd`;
      await c.env.BUCKET.put(key, body.mermaid, {
        httpMetadata: {
          contentType: 'text/plain; charset=utf-8'
        }
      });

      await c.env.PROCESSING_KV.put(`mermaid:${fileId}`, JSON.stringify({
        fileId,
        path: key,
        size: body.mermaid.length,
        savedAt: new Date().toISOString()
      }));

      return c.json({ success: true, fileId, path: key });
    } catch (error) {
      console.error('Save mermaid error:', error);
      return c.json({ error: 'Failed to save mermaid' }, 500);
    }
  });

  /**
   * GET /api/mermaid/:fileId
   * Load saved mermaid diagram source
   */
  app.get('/api/mermaid/:fileId', async (c) => {
    try {
      const fileId = c.req.param('fileId');
      if (!validateFileId(fileId)) {
        return c.json({ error: 'Invalid fileId format' }, 400);
      }

      const metaJson = await c.env.PROCESSING_KV.get(`mermaid:${fileId}`);
      if (!metaJson) {
        return c.json({ error: 'Mermaid not found' }, 404);
      }

      const meta = JSON.parse(metaJson);
      const obj = await c.env.BUCKET.get(meta.path);
      if (!obj) {
        return c.json({ error: 'Mermaid file not found in storage' }, 404);
      }

      const mermaid = await obj.text();
      return c.json({ ...meta, mermaid });
    } catch (error) {
      console.error('Get mermaid error:', error);
      return c.json({ error: 'Failed to get mermaid' }, 500);
    }
  });
}

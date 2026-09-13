/**
 * Results routes - save/fetch processing results (markdown)
 */
import { Hono } from 'hono';
import type { Env } from '../lib/types';
import { validateFileId } from '../lib/utils';

export function registerResultsRoutes(app: Hono<{ Bindings: Env }>) {
  /**
   * POST /api/results/:fileId
   * Save processing result (markdown text) to R2 + KV metadata
   */
  app.post('/api/results/:fileId', async (c) => {
    try {
      const fileId = c.req.param('fileId');
      if (!validateFileId(fileId)) {
        return c.json({ error: 'Invalid fileId format' }, 400);
      }

      const body = await c.req.json();
      if (typeof body.markdown !== 'string' || body.markdown.length === 0) {
        return c.json({ error: 'markdown field is required' }, 400);
      }

      if (body.markdown.length > 10 * 1024 * 1024) {
        return c.json({ error: 'Result too large (max 10MB)' }, 413);
      }

      // Save markdown to R2
      const key = `results/${fileId}/manual.md`;
      await c.env.BUCKET.put(key, body.markdown, {
        httpMetadata: {
          contentType: 'text/markdown; charset=utf-8'
        }
      });

      // Update KV metadata
      const resultMeta = {
        fileId,
        path: key,
        size: body.markdown.length,
        title: typeof body.title === 'string' ? body.title.slice(0, 300) : '',
        savedAt: new Date().toISOString()
      };
      await c.env.PROCESSING_KV.put(`result:${fileId}`, JSON.stringify(resultMeta));

      // Mark process as completed
      const processJson = await c.env.PROCESSING_KV.get(`process:${fileId}`);
      if (processJson) {
        const processState = JSON.parse(processJson);
        processState.status = 'completed';
        processState.progress = 100;
        processState.stage = '完了';
        processState.completedAt = new Date().toISOString();
        await c.env.PROCESSING_KV.put(`process:${fileId}`, JSON.stringify(processState));
      }

      return c.json({ success: true, fileId, path: key });
    } catch (error) {
      console.error('Save result error:', error);
      return c.json({ error: 'Failed to save result' }, 500);
    }
  });

  /**
   * GET /api/results/:fileId
   * Get result metadata + markdown content
   */
  app.get('/api/results/:fileId', async (c) => {
    try {
      const fileId = c.req.param('fileId');
      if (!validateFileId(fileId)) {
        return c.json({ error: 'Invalid fileId format' }, 400);
      }

      const metaJson = await c.env.PROCESSING_KV.get(`result:${fileId}`);
      if (!metaJson) {
        return c.json({ error: 'Result not found' }, 404);
      }

      const meta = JSON.parse(metaJson);
      const obj = await c.env.BUCKET.get(meta.path);
      if (!obj) {
        return c.json({ error: 'Result file not found in storage' }, 404);
      }

      const markdown = await obj.text();

      return c.json({ ...meta, markdown });
    } catch (error) {
      console.error('Get result error:', error);
      return c.json({ error: 'Failed to get result' }, 500);
    }
  });
}

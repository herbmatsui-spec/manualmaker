/**
 * Download routes - stream files from R2
 */
import { Hono } from 'hono';
import type { Env } from '../lib/types';
import { validateFileId, getContentType } from '../lib/utils';

export function registerDownloadRoutes(app: Hono<{ Bindings: Env }>) {
  /**
   * GET /api/download/:fileId/:type
   * type: pdf | md | markdown | html
   */
  app.get('/api/download/:fileId/:type', async (c) => {
    try {
      const fileId = c.req.param('fileId');
      const type = c.req.param('type');

      if (!validateFileId(fileId)) {
        return c.json({ error: 'Invalid fileId format' }, 400);
      }

      let key: string;
      if (type === 'pdf') {
        const metaJson = await c.env.PROCESSING_KV.get(`uploaded:${fileId}`);
        if (!metaJson) {
          return c.json({ error: 'Upload not found' }, 404);
        }
        const meta = JSON.parse(metaJson);
        key = meta.path;
      } else if (type === 'md' || type === 'markdown') {
        key = `results/${fileId}/manual.md`;
      } else {
        return c.json({ error: `Unsupported type: ${type}` }, 400);
      }

      const obj = await c.env.BUCKET.get(key);
      if (!obj) {
        return c.json({ error: 'File not found' }, 404);
      }

      const contentType = type === 'pdf' ? 'application/pdf' : getContentType(type);
      const ext = type === 'pdf' ? 'pdf' : 'md';
      const filename = `manual-${fileId.slice(0, 8)}.${ext}`;

      const headers = new Headers();
      obj.writeHttpMetadata(headers);
      headers.set('Content-Type', contentType);
      headers.set('Content-Disposition', `attachment; filename="${filename}"`);
      headers.set('ETag', obj.httpEtag);

      return new Response(obj.body, { headers });
    } catch (error) {
      console.error('Download error:', error);
      return c.json({ error: 'Download failed' }, 500);
    }
  });
}

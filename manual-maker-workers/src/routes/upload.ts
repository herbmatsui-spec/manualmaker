/**
 * Upload routes
 */
import { Hono } from 'hono';
import type { Env, UploadedFile } from '../lib/types';
import { uuidv4, isValidFilename } from '../lib/utils';

export function registerUploadRoutes(app: Hono<{ Bindings: Env }>) {
  app.post('/api/upload', async (c) => {
    try {
      const body = await c.req.parseBody();
      const file = body['file'];

      if (!file || !(file instanceof File)) {
        return c.json({ error: 'No file provided' }, 400);
      }

      const filename = file.name;
      if (!filename.toLowerCase().endsWith('.pdf')) {
        return c.json({ error: 'Only PDF files are allowed' }, 400);
      }

      if (!isValidFilename(filename)) {
        return c.json({ error: 'Invalid filename' }, 400);
      }

      const maxMb = parseInt(c.env.WEB_UPLOAD_MAX_MB || '100', 10);
      const maxSize = maxMb * 1024 * 1024;
      if (file.size > maxSize) {
        return c.json({
          error: `File size (${(file.size / 1024 / 1024).toFixed(1)}MB) exceeds limit (${maxMb}MB)`
        }, 400);
      }

      const fileId = uuidv4();
      const arrayBuffer = await file.arrayBuffer();

      // Upload to R2
      const key = `uploads/${fileId}/${filename}`;
      await c.env.BUCKET.put(key, arrayBuffer, {
        httpMetadata: {
          contentType: 'application/pdf'
        }
      });

      // Save metadata to KV
      const meta: UploadedFile = {
        fileId,
        filename,
        sizeMb: Math.round(file.size / 1024 / 1024 * 100) / 100,
        path: key,
        uploadedAt: new Date().toISOString()
      };

      await c.env.PROCESSING_KV.put(`uploaded:${fileId}`, JSON.stringify(meta));

      return c.json(meta);
    } catch (error) {
      console.error('Upload error:', error);
      return c.json({ error: 'Upload failed' }, 500);
    }
  });

  app.get('/api/uploads', async (c) => {
    try {
      const list = await c.env.PROCESSING_KV.list({ prefix: 'uploaded:' });
      const uploads: UploadedFile[] = [];

      for (const key of list.keys) {
        const data = await c.env.PROCESSING_KV.get(key.name, 'json');
        if (data) {
          uploads.push(data as UploadedFile);
        }
      }

      return c.json({ uploads });
    } catch (error) {
      console.error('List uploads error:', error);
      return c.json({ error: 'Failed to list uploads' }, 500);
    }
  });

  app.delete('/api/uploads/:fileId', async (c) => {
    try {
      const fileId = c.req.param('fileId');
      const metaJson = await c.env.PROCESSING_KV.get(`uploaded:${fileId}`);
      if (!metaJson) {
        return c.json({ error: 'Upload not found' }, 404);
      }

      const meta = JSON.parse(metaJson) as UploadedFile;
      await c.env.BUCKET.delete(meta.path);
      await c.env.PROCESSING_KV.delete(`uploaded:${fileId}`);

      return c.json({ success: true, fileId });
    } catch (error) {
      console.error('Delete upload error:', error);
      return c.json({ error: 'Failed to delete upload' }, 500);
    }
  });
}

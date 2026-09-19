/**
 * Results routes - save/fetch processing results (markdown)
 */
import { Hono } from 'hono';
import type { AppEnv } from '../lib/types';
import { validateFileId } from '../lib/utils';
import { ValidationError, NotFoundError } from '../lib/errors';
import { validate, getValidatedBody, getValidatedParams } from '../lib/validation';
import { bodyLimit } from '../lib/body-limit';
import { z } from 'zod';
import { openapiFileIdParam, openapiResultSaveBody } from '../lib/openapi-schemas';

export function registerResultsRoutes(app: Hono<AppEnv>) {
  /**
   * POST /api/results/:fileId
   * Save processing result (markdown text) to R2 + KV metadata
   */
  app.post('/api/results/:fileId',
    validate({
      params: openapiFileIdParam,
      body: openapiResultSaveBody
    }),
    bodyLimit({ maxSize: 12 * 1024 * 1024 }), // 12MB to accommodate JSON overhead
    async (c) => {
    const { fileId } = getValidatedParams<{ fileId: string }>(c);
    const { markdown, title } = getValidatedBody<{ markdown: string; title?: string }>(c);

    // Save markdown to R2
    const key = `results/${fileId}/manual.md`;
    await c.env.BUCKET.put(key, markdown, {
      httpMetadata: {
        contentType: 'text/markdown; charset=utf-8'
      }
    });

    // Update KV metadata
    const resultMeta = {
      fileId,
      path: key,
      size: markdown.length,
      title: typeof title === 'string' ? title.slice(0, 300) : '',
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
  }
);

  /**
   * GET /api/results/:fileId
   * Get result metadata + markdown content
   */
app.get('/api/results/:fileId',
   validate({
     params: openapiFileIdParam
   }),
   async (c) => {
    const { fileId } = getValidatedParams<{ fileId: string }>(c);

    const metaJson = await c.env.PROCESSING_KV.get(`result:${fileId}`);
    if (!metaJson) {
      throw new NotFoundError('Result');
    }

    const meta = JSON.parse(metaJson);
    const obj = await c.env.BUCKET.get(meta.path);
    if (!obj) {
      throw new NotFoundError('Result file not found in storage');
    }

    const markdown = await obj.text();

    return c.json({ ...meta, markdown });
  }
);
}

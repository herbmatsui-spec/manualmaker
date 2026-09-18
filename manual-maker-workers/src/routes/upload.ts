/**
 * Upload routes - streaming upload implementation
 */
import { Hono } from 'hono';
import type { AppEnv, UploadedFile } from '../lib/types';
import { uuidv4, isValidFilename, sanitizeFilename, validateFileId } from '../lib/utils';
import { NotFoundError } from '../lib/errors';
import { validate, getValidatedBody, getValidatedParams } from '../lib/validation';
import { z } from 'zod';
import { rateLimitUpload } from '../lib/rate-limit-middleware';
import { bodyLimit } from '../lib/body-limit';
import { createKVBatch } from '../lib/kv-batch';
import { createR2Replication } from '../lib/r2-replication';
import { openapiUploadBody } from '../lib/openapi-schemas';

export function registerUploadRoutes(app: Hono<AppEnv>) {
  app.post('/api/upload', rateLimitUpload(), 
    (c, next) => {
      // Calculate max size from environment variable, similar to existing logic
      const configuredMaxMb = Number(c.env.WEB_UPLOAD_MAX_MB);
      const maxSizeMb = Number.isFinite(configuredMaxMb) && configuredMaxMb > 0
        ? configuredMaxMb
        : 100;
      const maxSize = Math.floor(maxSizeMb * 1024 * 1024);
      
      // Apply body limit middleware
      return bodyLimit({ 
        maxSize,
        errorMessage: 'Uploaded file too large' 
      })(c, next);
    },
    validate({
      body: openapiUploadBody.refine(file => isValidFilename(file.file.name), {
        message: 'Invalid filename'
      })
    }),
    async (c) => {
      const requestId = c.get('requestId') || 'unknown';
      
// Get the validated file
       const body = getValidatedBody<{ file: File }>(c);
       const file = body.file;

       // Sanitize filename for safe usage
       const safeFilename = sanitizeFilename(file.name);

       const fileId = uuidv4();
       const key = `uploads/${fileId}/${safeFilename}`;

      // R2への転送はストリーム。先行するmultipart解析のバッファリングは別途発生する。
      await c.env.BUCKET.put(key, file.stream(), {
        httpMetadata: {
          contentType: 'application/pdf'
        }
      });

const meta: UploadedFile = {
         fileId,
         filename: safeFilename,
         sizeMb: Math.round(file.size / 1024 / 1024 * 100) / 100,
         path: key,
         uploadedAt: new Date().toISOString()
       };

      await c.env.PROCESSING_KV.put(`uploaded:${fileId}`, JSON.stringify(meta));

      if (c.env.BUCKET_SECONDARY) {
        const replication = createR2Replication(c.env).replicateObject(key).catch(() => {
          console.error(JSON.stringify({ event: 'r2_replication_failed', requestId, fileId }));
        });
        // Standalone Hono consumers may not provide a Workers execution context.
        let executionContext: Pick<ExecutionContext, 'waitUntil'> | undefined;
        try { executionContext = c.executionCtx; } catch { /* Use awaited fallback. */ }
        if (executionContext) executionContext.waitUntil(replication);
        else await replication;
      }

      return c.json(meta);
    }
  );

  app.get('/api/uploads', async (c) => {
    const kvBatch = createKVBatch(c.env);
    const records = await kvBatch.getByPrefix<UploadedFile>('uploaded:');
    const uploads = Object.values(records);
    return c.json({ uploads });
  });

app.delete('/api/uploads/:fileId', 
      validate({
        params: z.object({
          fileId: z.string().refine(validateFileId, {
            message: 'Invalid file ID'
          })
        })
      }),
      async (c) => {
        const fileId = getValidatedParams<{ fileId: string }>(c).fileId;
        const metaJson = await c.env.PROCESSING_KV.get(`uploaded:${fileId}`);
        if (!metaJson) {
          throw new NotFoundError('Upload');
        }

        const meta = JSON.parse(metaJson) as UploadedFile;
        await c.env.BUCKET.delete(meta.path);
        await c.env.PROCESSING_KV.delete(`uploaded:${fileId}`);

        return c.json({ success: true, fileId });
      }
    );
}
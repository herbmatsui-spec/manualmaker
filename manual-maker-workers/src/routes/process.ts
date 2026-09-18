/**
 * Process routes - client-offloaded processing
 * Workers only tracks processing state; heavy work happens client-side (PDF.js + Gemini)
 */
import { Hono } from 'hono';
import type { AppEnv, ProcessingResult, ProcessingOptions } from '../lib/types';
import { validateFileId } from '../lib/utils';
import { registerProgressRoutes } from './progress';
import { ValidationError, NotFoundError } from '../lib/errors';
import { validate, getValidatedBody, getValidatedParams } from '../lib/validation';
import { z } from 'zod';
import { fileIdParam, processStartBody, progressUpdateBody } from '../lib/schemas';
import { ProcessingState } from '../lib/progress-engine';
import { createKVBatch } from '../lib/kv-batch';
import { rateLimitProgressUpdate } from '../lib/rate-limit-middleware';

export function registerProcessRoutes(app: Hono<AppEnv>) {
  /**
   * POST /api/process/:fileId
   * Initialize processing state. Client will do the actual processing.
   */
app.post('/api/process/:fileId',
  validate({
    params: fileIdParam,
    body: processStartBody
  }),
  async (c) => {
    const { fileId } = getValidatedParams<{ fileId: string }>(c);
    const { options } = getValidatedBody<{ options: ProcessingOptions }>(c);
    // options is validated but not used in this endpoint; kept for future use

    const metaJson = await c.env.PROCESSING_KV.get(`uploaded:${fileId}`);
    if (!metaJson) {
      throw new NotFoundError('Upload');
    }

    const state: ProcessingResult = {
      fileId,
      status: 'processing',
      progress: 0,
      stage: '処理を開始しました',
      error: undefined
    };

    const id = c.env.PROGRESS_DO.idFromName(fileId);
    const stub = c.env.PROGRESS_DO.get(id);
    const requestId = c.get('requestId') || 'unknown';

    const processingState: ProcessingState = {
      ...state,
      updatedAt: new Date().toISOString()
    };

    let doSuccess = false;
    try {
      await stub.updateProgress(processingState);
      doSuccess = true;
    } catch (e: unknown) {
      console.warn(`[${requestId}] Failed to update DO progress:`, e);
    }

    if (!doSuccess) {
      // Fallback to KV
      const existingJson = await c.env.PROCESSING_KV.get(`process:${fileId}`);
      const existing = existingJson ? JSON.parse(existingJson) : {};
      await c.env.PROCESSING_KV.put(`process:${fileId}`, JSON.stringify({
        ...existing,
        ...state,
        updatedAt: new Date().toISOString()
      }));
    }

    return c.json(state);
  }
);

  /**
   * PUT /api/process/:fileId/progress
   * Update processing progress.
   */
app.put('/api/process/:fileId/progress',
  rateLimitProgressUpdate(),
  validate({
    params: fileIdParam,
    body: progressUpdateBody
  }),
  async (c) => {
    const { fileId } = getValidatedParams<{ fileId: string }>(c);
    const updates = getValidatedBody<ProcessingState>(c);

    const id = c.env.PROGRESS_DO.idFromName(fileId);
    const stub = c.env.PROGRESS_DO.get(id);
    const requestId = c.get('requestId') || 'unknown';

    // Fetch current state from DO to merge
    let current: ProcessingState | null = null;
    try {
      const currentState = await stub.queryProgress();
      if (currentState) {
        current = currentState;
      }
    } catch (e) {
      console.warn(`[${requestId}] Failed to query current progress:`, e);
    }

    const state: ProcessingState = {
      fileId,
      status: updates.status ?? current?.status ?? 'processing',
      progress: updates.progress ?? current?.progress ?? 0,
      stage: updates.stage ?? current?.stage ?? '',
      error: updates.error ?? current?.error,
      result: updates.result ?? current?.result,
      updatedAt: new Date().toISOString()
    };

    let doSuccess = false;
    try {
      await stub.updateProgress(state);
      doSuccess = true;
    } catch (e: unknown) {
      console.warn(`[${requestId}] Failed to update DO progress via PUT:`, e);
    }

    if (!doSuccess) {
      // Fallback to KV
      const existingJson = await c.env.PROCESSING_KV.get(`process:${fileId}`);
      const existing = existingJson ? JSON.parse(existingJson) : {};
      await c.env.PROCESSING_KV.put(`process:${fileId}`, JSON.stringify({
        ...existing,
        ...state,
        updatedAt: new Date().toISOString()
      }));
    }

    return c.json(state);
  }
);

  /**
   * GET /api/process/:fileId - get current processing state
   */
app.get('/api/process/:fileId',
  validate({
    params: fileIdParam
  }),
  async (c) => {
    const { fileId } = getValidatedParams<{ fileId: string }>(c);

    const id = c.env.PROGRESS_DO.idFromName(fileId);
    const stub = c.env.PROGRESS_DO.get(id);
    const requestId = c.get('requestId') || 'unknown';

    let state: ProcessingState | null = null;
    try {
      state = await stub.queryProgress();
    } catch (e) {
      console.warn(`[${requestId}] Failed to query progress from DO:`, e);
    }

    if (state) {
      return c.json(state);
    }

    // Fallback to KV
    const stateJson = await c.env.PROCESSING_KV.get(`process:${fileId}`, 'json');
    if (!stateJson) {
      throw new NotFoundError('Process');
    }

    return c.json(stateJson);
  }
);

   /**
    * GET /api/processes - get all processing states (admin/debug)
    */
    app.get('/api/processes', async (c) => {
      const kvBatch = createKVBatch(c.env);
      const records = await kvBatch.getByPrefix<ProcessingResult>('process:');
      const processes = Object.values(records);
      return c.json({ processes });
    });

   registerProgressRoutes(app);
}
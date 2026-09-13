/**
 * Process routes - client-offloaded processing
 * Workers only tracks processing state; heavy work happens client-side (PDF.js + Gemini)
 */
import { Hono } from 'hono';
import type { Env, ProcessingResult } from '../lib/types';
import { validateFileId } from '../lib/utils';

export function registerProcessRoutes(app: Hono<{ Bindings: Env }>) {
  /**
   * POST /api/process/:fileId
   * Initialize processing state. Client will do the actual processing.
   */
  app.post('/api/process/:fileId', async (c) => {
    try {
      const fileId = c.req.param('fileId');
      if (!validateFileId(fileId)) {
        return c.json({ error: 'Invalid fileId format' }, 400);
      }

      const metaJson = await c.env.PROCESSING_KV.get(`uploaded:${fileId}`);
      if (!metaJson) {
        return c.json({ error: 'Upload not found' }, 404);
      }

      const body = await c.req.json().catch(() => ({}));

      const state: ProcessingResult = {
        fileId,
        status: 'processing',
        progress: 0,
        stage: '処理を開始しました',
        error: undefined
      };

      await c.env.PROCESSING_KV.put(`process:${fileId}`, JSON.stringify({
        ...state,
        options: body.options || {},
        startedAt: new Date().toISOString()
      }));

      return c.json(state);
    } catch (error) {
      console.error('Process init error:', error);
      return c.json({ error: 'Failed to initialize processing' }, 500);
    }
  });

  /**
   * PUT /api/process/:fileId/progress
   * Update progress from client during processing
   */
  app.put('/api/process/:fileId/progress', async (c) => {
    try {
      const fileId = c.req.param('fileId');
      if (!validateFileId(fileId)) {
        return c.json({ error: 'Invalid fileId format' }, 400);
      }

      const existing = await c.env.PROCESSING_KV.get(`process:${fileId}`);
      if (!existing) {
        return c.json({ error: 'Process not found' }, 404);
      }

      const body = await c.req.json();
      const progress = Math.max(0, Math.min(100, Number(body.progress) || 0));
      const stage = typeof body.stage === 'string' ? body.stage.slice(0, 200) : '';
      const status = ['pending', 'processing', 'completed', 'failed'].includes(body.status)
        ? body.status
        : 'processing';

      const state: ProcessingResult = {
        fileId,
        status,
        progress,
        stage,
        result: body.result,
        error: body.error
      };

      await c.env.PROCESSING_KV.put(`process:${fileId}`, JSON.stringify({
        ...JSON.parse(existing),
        ...state,
        updatedAt: new Date().toISOString()
      }));

      return c.json(state);
    } catch (error) {
      console.error('Progress update error:', error);
      return c.json({ error: 'Failed to update progress' }, 500);
    }
  });

  /**
   * GET /api/process/:fileId - get current processing state
   */
  app.get('/api/process/:fileId', async (c) => {
    try {
      const fileId = c.req.param('fileId');
      if (!validateFileId(fileId)) {
        return c.json({ error: 'Invalid fileId format' }, 400);
      }

      const state = await c.env.PROCESSING_KV.get(`process:${fileId}`, 'json');
      if (!state) {
        return c.json({ error: 'Process not found' }, 404);
      }

      return c.json(state);
    } catch (error) {
      console.error('Get process error:', error);
      return c.json({ error: 'Failed to get processing state' }, 500);
    }
  });
}

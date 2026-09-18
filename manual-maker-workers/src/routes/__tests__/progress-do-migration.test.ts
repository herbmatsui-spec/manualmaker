import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Hono } from 'hono';
import type { AppEnv, Env } from '../../lib/types';
import { registerProcessRoutes } from '../process';
import { ProcessingState } from '../../lib/progress-engine';
import { correlationId, errorHandler } from '../../lib/middleware';

const kvGet = vi.fn();
const kvPut = vi.fn();
const kvDelete = vi.fn();
const doIdFromName = vi.fn((name: string) => name);
const doGet = vi.fn();

let kvProcessValue: unknown = null;

const mockEnv = {
  BUCKET: {}, // not used in these tests
  PROCESSING_KV: { get: kvGet, put: kvPut, delete: kvDelete },
  PROGRESS_DO: { idFromName: doIdFromName, get: doGet },
  GEMINI_API_KEY: 'test',
  GOOGLE_API_KEY: 'test',
  GOOGLE_CLOUD_PROJECT_ID: 'test',
  RATE_LIMIT_ENABLED: 'false'
} as unknown as Env;

function createTestApp() {
  const app = new Hono<AppEnv>();
  app.onError((error) => { throw error; });
  app.use('*', correlationId());
  app.use('*', errorHandler());
  return app;
}

const createMockDOStub = () => ({
  updateProgress: vi.fn(),
  queryProgress: vi.fn(),
  fetch: vi.fn()
});

describe('Progress DO Migration', () => {
  let app: Hono<AppEnv>;

  beforeEach(() => {
    vi.clearAllMocks();
    kvProcessValue = null;
    kvGet.mockImplementation(async (key: string) => {
      if (key.startsWith('uploaded:')) {
        return JSON.stringify({ path: `uploads/${key.slice('uploaded:'.length)}/test.pdf` });
      }
      return kvProcessValue;
    });
    app = createTestApp();
    registerProcessRoutes(app);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('POST /api/process/:fileId', () => {
    it('should update DO successfully and not fallback to KV', async () => {
      const fileId = 'a'.repeat(32);
      const mockStub = createMockDOStub();
      mockStub.updateProgress.mockResolvedValue(undefined);
      doGet.mockReturnValue(mockStub);

      const res = await app.request(
        `http://localhost/api/process/${fileId}`, {
          method: 'POST',
          body: JSON.stringify({ options: {} }),
          headers: { 'Content-Type': 'application/json' }
        }, mockEnv
      );

      expect(res.status).toBe(200);
      const json = await res.json();
      expect(json).toMatchObject({
        fileId,
        status: 'processing',
        progress: 0,
        stage: '処理を開始しました'
      });

      expect(mockStub.updateProgress).toHaveBeenCalledTimes(1);
      const callArg = mockStub.updateProgress.mock.calls[0][0];
      expect(callArg).toMatchObject({
        fileId,
        status: 'processing',
        progress: 0,
        stage: '処理を開始しました'
      });
      expect(callArg.updatedAt).toBeDefined();

      expect(doIdFromName).toHaveBeenCalledExactlyOnceWith(fileId);
      expect(doGet).toHaveBeenCalledExactlyOnceWith(fileId);
      expect(kvGet).toHaveBeenCalledExactlyOnceWith(`uploaded:${fileId}`);
      expect(kvPut).not.toHaveBeenCalled();
    });

    it('should fallback to KV when DO update fails', async () => {
      const fileId = 'b'.repeat(32);
      const mockStub = createMockDOStub();
      mockStub.updateProgress.mockRejectedValue(new Error('DO failure'));
      doGet.mockReturnValue(mockStub);

      const res = await app.request(
        `http://localhost/api/process/${fileId}`, {
          method: 'POST',
          body: JSON.stringify({ options: {} }),
          headers: { 'Content-Type': 'application/json' }
        }, mockEnv
      );

      expect(res.status).toBe(200);
      const json = await res.json();
      expect(json).toMatchObject({
        fileId,
        status: 'processing',
        progress: 0,
        stage: '処理を開始しました'
      });

      expect(mockStub.updateProgress).toHaveBeenCalledTimes(1);

      // KV put should be called as fallback
      expect(kvPut).toHaveBeenCalledTimes(1);
      const putArgs = kvPut.mock.calls[0];
      expect(putArgs[0]).toBe(`process:${fileId}`);
      const putBody = JSON.parse(putArgs[1]);
      expect(putBody).toMatchObject({
        fileId,
        status: 'processing',
        progress: 0,
        stage: '処理を開始しました'
      });
      expect(putBody.updatedAt).toBeDefined();
    });
  });

  describe('PUT /api/process/:fileId/progress', () => {
    it('should update DO successfully and not fallback to KV', async () => {
      const fileId = 'c'.repeat(32);
      const mockStub = createMockDOStub();
      const existingState: ProcessingState = {
        fileId,
        status: 'processing',
        progress: 10,
        stage: '半分処理',
        error: undefined,
        result: undefined,
        updatedAt: new Date().toISOString()
      };
      mockStub.queryProgress.mockResolvedValue(existingState);
      mockStub.updateProgress.mockResolvedValue(undefined);
      doGet.mockReturnValue(mockStub);

      const res = await app.request(
        `http://localhost/api/process/${fileId}/progress`, {
          method: 'PUT',
          body: JSON.stringify({ progress: 50, stage: 'ほぼ完了' }),
          headers: { 'Content-Type': 'application/json' }
        }, mockEnv
      );

      expect(res.status).toBe(200);
      const json = await res.json();
      expect(json).toMatchObject({
        fileId,
        status: 'processing',
        progress: 50,
        stage: 'ほぼ完了'
      });

      expect(mockStub.queryProgress).toHaveBeenCalledTimes(1);
      expect(mockStub.updateProgress).toHaveBeenCalledTimes(1);
      const updateArg = mockStub.updateProgress.mock.calls[0][0];
      expect(updateArg).toMatchObject({
        fileId,
        status: 'processing',
        progress: 50,
        stage: 'ほぼ完了'
      });
      expect(updateArg.updatedAt).toBeDefined();

      expect(kvPut).not.toHaveBeenCalled();
    });

    it('should fallback to KV when DO update fails', async () => {
      const fileId = 'd'.repeat(32);
      const mockStub = createMockDOStub();
      mockStub.queryProgress.mockResolvedValue(null);
      mockStub.updateProgress.mockRejectedValue(new Error('DO failure'));
      doGet.mockReturnValue(mockStub);

      const res = await app.request(
        `http://localhost/api/process/${fileId}/progress`, {
          method: 'PUT',
          body: JSON.stringify({ progress: 30 }),
          headers: { 'Content-Type': 'application/json' }
        }, mockEnv
      );

      expect(res.status).toBe(200);
      const json = await res.json();
      expect(json).toMatchObject({
        fileId,
        status: 'processing',
        progress: 30,
        stage: ''
      });

      expect(mockStub.queryProgress).toHaveBeenCalledTimes(1);
      expect(mockStub.updateProgress).toHaveBeenCalledTimes(1);

      expect(kvPut).toHaveBeenCalledTimes(1);
      const putArgs = kvPut.mock.calls[0];
      expect(putArgs[0]).toBe(`process:${fileId}`);
      const putBody = JSON.parse(putArgs[1]);
      expect(putBody).toMatchObject({
        fileId,
        status: 'processing',
        progress: 30,
        stage: ''
      });
      expect(putBody.updatedAt).toBeDefined();
    });
  });

  describe('GET /api/process/:fileId', () => {
    it('should return state from DO when available', async () => {
      const fileId = 'e'.repeat(32);
      const mockStub = createMockDOStub();
      const doState: ProcessingState = {
        fileId,
        status: 'completed',
        progress: 100,
        stage: '完了',
        result: { markdown: '# hello' },
        updatedAt: new Date().toISOString()
      };
      mockStub.queryProgress.mockResolvedValue(doState);
      doGet.mockReturnValue(mockStub);

      const res = await app.request(
        `http://localhost/api/process/${fileId}`, { method: 'GET' }, mockEnv
      );

      expect(res.status).toBe(200);
      const json = await res.json();
      expect(json).toMatchObject(doState);

      expect(mockStub.queryProgress).toHaveBeenCalledTimes(1);
      expect(kvGet).not.toHaveBeenCalled();
    });

    it('should fallback to KV when DO returns null', async () => {
      const fileId = 'f'.repeat(32);
      const mockStub = createMockDOStub();
      mockStub.queryProgress.mockResolvedValue(null);
      doGet.mockReturnValue(mockStub);

      const kvState = {
        fileId,
        status: 'failed',
        progress: 0,
        stage: 'エラー',
        error: '何かが壊れた',
        updatedAt: new Date().toISOString()
      };
      kvProcessValue = kvState;

      const res = await app.request(
        `http://localhost/api/process/${fileId}`, { method: 'GET' }, mockEnv
      );

      expect(res.status).toBe(200);
      const json = await res.json();
      expect(json).toMatchObject(kvState);

      expect(mockStub.queryProgress).toHaveBeenCalledTimes(1);
      expect(kvGet).toHaveBeenCalledTimes(1);
      expect(kvGet).toHaveBeenCalledWith(`process:${fileId}`, 'json');
    });

    it('should return 404 when both DO and KV have no state', async () => {
      const fileId = '1'.repeat(32);
      const mockStub = createMockDOStub();
      mockStub.queryProgress.mockResolvedValue(null);
      doGet.mockReturnValue(mockStub);

      const res = await app.request(
        `http://localhost/api/process/${fileId}`, { method: 'GET' }, mockEnv
      );

      expect(res.status).toBe(404);
      expect(await res.json()).toEqual({ error: {
        code: 'NOT_FOUND', message: 'Process not found', requestId: res.headers.get('x-request-id')
      } });
      expect(doIdFromName).toHaveBeenCalledExactlyOnceWith(fileId);
      expect(doGet).toHaveBeenCalledExactlyOnceWith(fileId);
      expect(mockStub.queryProgress).toHaveBeenCalledTimes(1);
      expect(kvGet).toHaveBeenCalledExactlyOnceWith(`process:${fileId}`, 'json');
    });
  });
});

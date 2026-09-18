/**
 * Download routes - stream files from R2
 */
import { Hono } from 'hono';
import type { AppEnv } from '../lib/types';
import { validateFileId, getContentType } from '../lib/utils';
import { ValidationError, NotFoundError } from '../lib/errors';

function parseRangeHeader(header: string, total: number): { start: number; end: number } | null {
  const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  if (!match || (!match[1] && !match[2]) || total === 0) return null;
  const first = match[1] ? Number(match[1]) : undefined;
  const last = match[2] ? Number(match[2]) : undefined;
  if ([first, last].some(value => value !== undefined && !Number.isSafeInteger(value))) return null;
  if (first === undefined) {
    if (!last) return null;
    return { start: Math.max(0, total - last), end: total - 1 };
  }
  if (first >= total || (last !== undefined && last < first)) return null;
  return { start: first, end: Math.min(last ?? total - 1, total - 1) };
}

export function registerDownloadRoutes(app: Hono<AppEnv>) {
  /**
   * GET /api/download/:fileId/:type
   * type: pdf | md | markdown
   */
  app.get('/api/download/:fileId/:type', async (c) => {
    const fileId = c.req.param('fileId');
    const type = c.req.param('type');

    if (!validateFileId(fileId)) {
      throw new ValidationError('Invalid fileId format');
    }

    let key: string;
    if (type === 'pdf') {
      const metaJson = await c.env.PROCESSING_KV.get(`uploaded:${fileId}`);
      if (!metaJson) {
        throw new NotFoundError('Upload');
      }
      const meta = JSON.parse(metaJson);
      key = meta.path;
    } else if (type === 'md' || type === 'markdown') {
      key = `results/${fileId}/manual.md`;
    } else {
      throw new ValidationError(`Unsupported type: ${type}`);
    }

    // Rangeリクエスト処理
    const rangeHeader = c.req.header('range');

    // 通常取得は一度だけ。Rangeのサイズ検証時のみheadを使う。
    const fullObject = rangeHeader === undefined ? await c.env.BUCKET.get(key) : null;
    const head = rangeHeader === undefined ? fullObject : await c.env.BUCKET.head(key);
    if (!head) {
      throw new NotFoundError('File not found');
    }
    const totalSize = head.size;

    const headers = new Headers();
    headers.set('Content-Type', type === 'pdf' ? 'application/pdf' : getContentType(type));
    headers.set('Content-Disposition', `attachment; filename="${fileId.slice(0, 8)}.${type === 'pdf' ? 'pdf' : 'md'}"`);
    if (head.httpEtag) headers.set('ETag', head.httpEtag);
    headers.set('Accept-Ranges', 'bytes');

    if (rangeHeader !== undefined) {
      const range = parseRangeHeader(rangeHeader, totalSize);
      if (!range) {
        headers.set('Content-Range', `bytes */${totalSize}`);
        return new Response(null, { status: 416, headers });
      }
      const { start, end } = range;
      const length = end - start + 1;
      const obj = await c.env.BUCKET.get(key, { range: { offset: start, length } });
      if (!obj) {
        throw new NotFoundError('File not found');
      }

      if (obj.httpEtag) headers.set('ETag', obj.httpEtag);
      headers.set('Content-Range', `bytes ${start}-${end}/${totalSize}`);
      headers.set('Content-Length', String(length));

      return new Response(obj.body, { status: 206, headers });
    }

    // 通常取得（フルファイル）
    const obj = fullObject;
    if (!obj) {
      throw new NotFoundError('File not found');
    }

    // Keep the route's download content type/disposition rather than stored inline metadata.
    headers.set('Content-Length', String(totalSize));

    return new Response(obj.body, { status: 200, headers });
  });
}
import { Hono } from 'hono';
import type { AppEnv } from '../lib/types';
import { validate, getValidatedParams } from '../lib/validation';
import { openapiFileIdParam } from '../lib/openapi-schemas';
import { NotFoundError } from '../lib/errors';

export function registerProgressRoutes(app: Hono<AppEnv>) {
   app.get('/api/progress/:fileId', async (c) => {
     const requestId = c.get('requestId') || 'unknown';
     try {
       const id = c.env.PROGRESS_DO.idFromName(c.req.param('fileId'));
       const stub = c.env.PROGRESS_DO.get(id);

       return stub.fetch(c.req.raw);
     } catch (err) {
       console.error(`[${requestId}] Progress WebSocket error:`, err);
       return c.json({ error: 'Failed to establish progress connection' }, 500);
     }
   });

   app.get('/api/progress/:fileId/http',
     validate({ params: openapiFileIdParam }),
     async (c) => {
       const { fileId } = getValidatedParams<{ fileId: string }>(c);
       const id = c.env.PROGRESS_DO.idFromName(fileId);
       const stub = c.env.PROGRESS_DO.get(id);
       const state = await stub.queryProgress();
       if (!state) throw new NotFoundError('Progress');
       return c.json(state);
     }
   );
 }
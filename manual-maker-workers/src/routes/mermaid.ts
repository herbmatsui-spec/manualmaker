/**
 * Mermaid routes - metadata only (rendering/validation happens client-side)
 */
import { OpenAPIHono } from '@hono/zod-openapi';
import type { AppEnv } from '../lib/types';
import { validateFileId } from '../lib/utils';
import { z } from 'zod';
import { ValidationError, NotFoundError } from '../lib/errors';
import { 
  ValidationErrorResponseSchema, 
  NotFoundErrorResponseSchema, 
  InternalErrorResponseSchema 
} from '../lib/openapi-errors';
import { openapiFileIdParam, openapiMermaidSaveBody } from '../lib/openapi-schemas';

export function registerMermaidRoutes(app: OpenAPIHono<AppEnv>) {
  /**
   * POST /api/mermaid/save/:fileId
   * Save edited mermaid diagram source
   */
app.openapi({
       path: '/api/mermaid/save/{fileId}',
       method: 'post',

       summary: 'Save Mermaid diagram',
       description: 'Save edited mermaid diagram source',
request: {
          params: openapiFileIdParam,
           body: {
             required: true,
             content: {
              'application/json': {
                 schema: openapiMermaidSaveBody
              }
            }
          }
        },
       responses: {
         '200': {
           description: 'Mermaid saved successfully',
           content: {
             'application/json': {
               schema: z.object({
                 success: z.boolean(),
                 fileId: z.string(),
                 path: z.string()
               })
             }
           }
         },
         '400': {
           description: 'Validation error',
           content: {
             'application/json': {
               schema: ValidationErrorResponseSchema
             }
           }
         },
         '413': {
           description: 'Mermaid source too large',
           content: {
             'application/json': {
               schema: ValidationErrorResponseSchema
             }
           }
         },
         '500': {
           description: 'Internal server error',
           content: {
             'application/json': {
               schema: InternalErrorResponseSchema
             }
           }
         }
       }
     },
     async (c) => {
       const { fileId } = c.req.valid('param');
       const { mermaid } = c.req.valid('json');

       const key = `results/${fileId}/diagram.mmd`;
       await c.env.BUCKET.put(key, mermaid, {
         httpMetadata: {
           contentType: 'text/plain; charset=utf-8'
         }
       });

       await c.env.PROCESSING_KV.put(`mermaid:${fileId}`, JSON.stringify({
         fileId,
         path: key,
         size: mermaid.length,
         savedAt: new Date().toISOString()
       }));

       return c.json({ success: true, fileId, path: key });
     }
   );

  /**
   * GET /api/mermaid/:fileId
   * Load saved mermaid diagram source
   */
app.openapi({
       path: '/api/mermaid/{fileId}',
       method: 'get',

       summary: 'Load Mermaid diagram',
       description: 'Load saved mermaid diagram source',
       request: {
         params: openapiFileIdParam
       },
       responses: {
         '200': {
           description: 'Mermaid diagram source',
           content: {
             'application/json': {
               schema: z.object({
                 fileId: z.string(),
                 path: z.string(),
                 size: z.number().int(),
                 savedAt: z.string(),
                 mermaid: z.string()
               })
             }
           }
         },
         '400': {
           description: 'Validation error',
           content: {
             'application/json': {
               schema: ValidationErrorResponseSchema
             }
           }
         },
         '404': {
           description: 'Mermaid not found',
           content: {
             'application/json': {
               schema: NotFoundErrorResponseSchema
             }
           }
         },
         '500': {
           description: 'Internal server error',
           content: {
             'application/json': {
               schema: InternalErrorResponseSchema
             }
           }
         }
       }
     },
     async (c) => {
       const { fileId } = c.req.valid('param');

       const metaJson = await c.env.PROCESSING_KV.get(`mermaid:${fileId}`);
       if (!metaJson) {
         throw new NotFoundError('Mermaid');
       }

       const meta = JSON.parse(metaJson);
       const obj = await c.env.BUCKET.get(meta.path);
       if (!obj) {
         throw new NotFoundError('Mermaid file not found in storage');
       }

       const mermaid = await obj.text();
       return c.json({ ...meta, mermaid });
     }
   );
}
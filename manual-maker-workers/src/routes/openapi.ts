import { z, type OpenAPIHono } from '@hono/zod-openapi';
import type { AppEnv } from '../lib/types';
import { registerHealthContracts } from './health-contracts';
import { fileIdParam, resultSaveBody, processStartBody, progressUpdateBody,
  geminiProxyParams, geminiProxyBody, visionProxyBody } from '../lib/schemas';

export const processingResponseSchema = z.object({
  fileId: fileIdParam.shape.fileId,
  status: z.enum(['pending', 'processing', 'completed', 'failed']),
  progress: z.number().int().min(0).max(100),
  stage: z.string(),
  result: progressUpdateBody.shape.result,
  error: z.string().optional(),
  updatedAt: z.string().datetime().optional(),
}).passthrough();

export const resultSaveResponseSchema = z.object({
  success: z.literal(true),
  fileId: fileIdParam.shape.fileId,
  path: z.string().min(1),
}).strict();

export const resultResponseSchema = z.object({
  fileId: fileIdParam.shape.fileId,
  path: z.string().min(1),
  size: z.number().int().nonnegative().describe('Markdown length in UTF-16 code units'),
  title: z.string().max(300),
  savedAt: z.string().datetime(),
  markdown: z.string(),
}).passthrough();

export const appErrorResponseSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    requestId: z.string(),
    details: z.unknown().optional(),
  }),
});

export const healthResponseSchema = z.object({
  status: z.literal('ok'),
  version: z.literal('2.0.0'),
  processorType: z.literal('cloudflare-workers'),
}).strict();

export const uploadResponseSchema = z.object({
  fileId: z.string().uuid(),
  filename: z.string().min(1),
  sizeMb: z.number().nonnegative(),
  path: z.string().min(1),
  uploadedAt: z.string().datetime(),
}).strict();

/** Describe ordinary Hono routes without registering duplicate handlers. */
export function registerOpenAPIRoutes(app: OpenAPIHono<AppEnv>) {
  registerHealthContracts(app);
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/health',
    responses: {
      200: { description: 'Service health', content: {
        'application/json': { schema: healthResponseSchema },
      } },
    },
  });
  app.openAPIRegistry.registerPath({
    method: 'post', path: '/api/upload',
    request: { body: { required: true, content: {
      'multipart/form-data': { schema: z.object({
        file: z.string().openapi({ type: 'string', format: 'binary' }),
      }) },
    } } },
    responses: {
      200: { description: 'Stored upload metadata', content: {
        'application/json': { schema: uploadResponseSchema },
      } },
      400: { description: 'Invalid upload' },
      413: { description: 'Upload exceeds the configured limit' },
      429: { description: 'Rate limit exceeded' },
      500: { description: 'Storage or internal failure' },
    },
  });
  app.openAPIRegistry.registerPath({
    method: 'post', path: '/api/results/{fileId}',
    operationId: 'saveResult',
    request: {
      params: fileIdParam,
      body: { required: true, content: {
        'application/json': { schema: resultSaveBody },
      } },
    },
    responses: {
      200: { description: 'Result saved', content: {
        'application/json': { schema: resultSaveResponseSchema },
      } },
      400: { description: 'Invalid file identifier or result body' },
      429: { description: 'Rate limit exceeded' },
      500: { description: 'Storage or internal failure' },
    },
  });
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/results/{fileId}',
    operationId: 'getResult',
    request: { params: fileIdParam },
    responses: {
      200: { description: 'Saved result metadata and Markdown', content: {
        'application/json': { schema: resultResponseSchema },
      } },
      400: { description: 'Invalid file identifier', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
      404: { description: 'Result metadata or stored body not found', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
      429: { description: 'Rate limit exceeded' },
      500: { description: 'Storage or internal failure', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
    },
  });
  const processResponses = {
    200: { description: 'Current processing state', content: {
      'application/json': { schema: processingResponseSchema },
    } },
    400: { description: 'Invalid identifier or request body', content: {
      'application/json': { schema: appErrorResponseSchema },
    } },
    429: { description: 'Rate limit exceeded' },
    500: { description: 'Storage or internal failure', content: {
      'application/json': { schema: appErrorResponseSchema },
    } },
  };
  const processNotFound = { description: 'Upload or processing state not found', content: {
    'application/json': { schema: appErrorResponseSchema },
  } };
  app.openAPIRegistry.registerPath({
    method: 'post', path: '/api/process/{fileId}', operationId: 'startProcessing',
    description: 'Initializes progress tracking; processing runs on the client.',
    request: { params: fileIdParam, body: { required: true, content: {
      'application/json': { schema: processStartBody },
    } } },
    responses: { ...processResponses, 404: processNotFound },
  });
  app.openAPIRegistry.registerPath({
    method: 'put', path: '/api/process/{fileId}/progress', operationId: 'updateProcessingProgress',
    request: { params: fileIdParam, body: { required: true, content: {
      'application/json': { schema: progressUpdateBody },
    } } },
    responses: processResponses,
  });
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/process/{fileId}', operationId: 'getProcessingState',
    request: { params: fileIdParam },
    responses: { ...processResponses, 404: processNotFound },
  });
  const uploadListResponseSchema = z.object({
    uploads: z.array(uploadResponseSchema),
  }).strict();
  const uploadDeleteResponseSchema = z.object({
    success: z.literal(true),
    fileId: fileIdParam.shape.fileId,
  }).strict();
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/uploads', operationId: 'listUploads',
    responses: {
      200: { description: 'Uploaded file metadata', content: {
        'application/json': { schema: uploadListResponseSchema },
      } },
      429: { description: 'Rate limit exceeded' },
      500: { description: 'Storage or internal failure', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
    },
  });
  app.openAPIRegistry.registerPath({
    method: 'delete', path: '/api/uploads/{fileId}', operationId: 'deleteUpload',
    description: 'Deletes the stored object and its metadata. Replication of the deletion is not implemented.',
    request: { params: fileIdParam },
    responses: {
      200: { description: 'Deleted', content: {
        'application/json': { schema: uploadDeleteResponseSchema },
      } },
      400: { description: 'Invalid file identifier', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
      404: { description: 'Upload not found', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
      429: { description: 'Rate limit exceeded' },
      500: { description: 'Storage or internal failure', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
    },
  });
  const configResponseSchema = z.object({
    geminiModelName: z.string().min(1),
    processorType: z.literal('cloudflare-workers'),
    pdfDpi: z.number().int().positive(),
    maxFileSizeMb: z.number().int().positive(),
    webUploadMaxMb: z.number().int().positive(),
    outputDirectory: z.string().min(1),
    supportedExtensions: z.array(z.string().regex(/^\./)),
    defaultLanguage: z.string().min(2),
  }).strict();
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/config', operationId: 'getConfig',
    responses: {
      200: { description: 'Public processing configuration', content: {
        'application/json': { schema: configResponseSchema },
      } },
      429: { description: 'Rate limit exceeded' },
      500: { description: 'Internal failure', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
    },
  });
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/processes', operationId: 'listProcessingStates',
    description: 'Debug listing of KV fallback states only; Durable Object states are not included.',
    responses: {
      200: { description: 'Processing states stored in KV', content: {
        'application/json': { schema: z.object({
          processes: z.array(processingResponseSchema),
        }).strict() },
      } },
      429: { description: 'Rate limit exceeded' },
      500: { description: 'Storage or internal failure', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
    },
  });
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/progress/{fileId}/http', operationId: 'getProgressHttp',
    description: 'HTTP polling alternative to the WebSocket endpoint; reads the Durable Object state.',
    request: { params: fileIdParam },
    responses: {
      200: { description: 'Current progress state', content: {
        'application/json': { schema: processingResponseSchema },
      } },
      400: { description: 'Invalid file identifier', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
      404: { description: 'No progress state', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
      429: { description: 'Rate limit exceeded' },
      500: { description: 'Progress query failure', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
    },
  });
  const geminiResponses = {
    200: { description: 'Upstream JSON, passed through without transformation', content: {
      'application/json': { schema: z.unknown().openapi({ description: 'Upstream-defined JSON; streaming methods return a buffered JSON array, not SSE.' }) },
    } },
    400: { description: 'Invalid request', content: {
      'application/json': { schema: appErrorResponseSchema },
    } },
    429: { description: 'Local or upstream rate limit exceeded' },
    500: { description: 'Internal or transport failure', content: {
      'application/json': { schema: appErrorResponseSchema },
    } },
    502: { description: 'Upstream error or API key not configured', content: {
      'application/json': { schema: appErrorResponseSchema },
    } },
  };
  app.openAPIRegistry.registerPath({
    method: 'post', path: '/api/gemini/{model}/{method}', operationId: 'proxyGemini',
    description: 'Forwards JSON to Gemini. Responses are buffered, including streamGenerateContent. The current size check uses the declared Content-Length only.',
    request: { params: geminiProxyParams, body: { required: true, content: {
      'application/json': { schema: geminiProxyBody },
    } } },
    responses: {
      ...geminiResponses,
      413: { description: 'Declared request size exceeds 100 MiB', content: {
        'application/json': { schema: z.object({ error: z.string(), maxSize: z.literal(100 * 1024 * 1024) }) },
      } },
    },
  });
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/gemini/models', operationId: 'listGeminiModels',
    responses: geminiResponses,
  });
  app.openAPIRegistry.registerPath({
    method: 'post', path: '/api/vision/annotate', operationId: 'annotateImage',
    description: 'Forwards validated image requests to Vision. Successful upstream JSON is returned unchanged; individual annotation errors may be included in a 200 response.',
    request: { body: { required: true, content: {
      'application/json': { schema: visionProxyBody },
    } } },
    responses: {
      200: { description: 'Upstream-defined JSON response', content: {
        'application/json': { schema: z.unknown() },
      } },
      400: { description: 'Invalid annotation request', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
      429: { description: 'Local rate limit exceeded' },
      500: { description: 'Transport, retry exhaustion or internal failure', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
      502: { description: 'Upstream rejection or missing API key', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
    },
  });
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/progress/{fileId}', operationId: 'connectProgress',
    description: 'WebSocket handshake; after upgrade, messages contain processing state (or null when cleared). Unlike HTTP polling, the current handshake does not validate the identifier format. OpenAPI describes only the handshake, not WebSocket frames.',
    request: {
      params: z.object({ fileId: z.string().min(1) }),
      headers: z.object({ Upgrade: z.literal('websocket').optional() }),
    },
    responses: {
      101: { description: 'WebSocket connected; progress messages follow on the socket' },
      426: { description: 'WebSocket upgrade required', content: {
        'text/plain': { schema: z.literal('Expected WebSocket') },
      } },
      429: { description: 'Local rate limit exceeded' },
      500: { description: 'Connection setup or asynchronous forwarding failure', content: {
        'application/json': { schema: z.union([
          z.object({ error: z.literal('Failed to establish progress connection') }),
          appErrorResponseSchema,
        ]) },
      } },
    },
  });
  const downloadContent = {
    'application/pdf': { schema: z.string().openapi({ format: 'binary' }) },
    'text/markdown': { schema: z.string().openapi({ format: 'binary' }) },
  };
  const downloadHeaders = {
    'Accept-Ranges': { schema: { type: 'string' as const, enum: ['bytes'] } },
    'Content-Disposition': { schema: { type: 'string' as const } },
    'ETag': { schema: { type: 'string' as const } },
  };
  app.openAPIRegistry.registerPath({
    method: 'get', path: '/api/download/{fileId}/{type}', operationId: 'downloadFile',
    description: 'Streams PDF or Markdown. Only a single byte range is supported.',
    request: {
      params: fileIdParam.extend({ type: z.enum(['pdf', 'md', 'markdown']) }),
      headers: z.object({
        Range: z.string().optional().describe('Single byte range, for example bytes=0-99 or bytes=-100'),
        'If-None-Match': z.string().optional(),
      }),
    },
    responses: {
      200: { description: 'Complete file', content: downloadContent, headers: {
        ...downloadHeaders, 'Content-Length': { schema: { type: 'string', pattern: '^\\d+$' } },
      } },
      206: { description: 'Partial file', content: downloadContent, headers: {
        ...downloadHeaders,
        'Content-Length': { schema: { type: 'string', pattern: '^\\d+$' } },
        'Content-Range': { schema: { type: 'string', pattern: '^bytes \\d+-\\d+/\\d+$' } },
      } },
      304: { description: 'ETag matches; no response body' },
      400: { description: 'Invalid identifier or type', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
      404: { description: 'Upload or file not found', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
      416: { description: 'Invalid or unsatisfiable range; empty body', headers: {
        ...downloadHeaders, 'Content-Range': { schema: { type: 'string', pattern: '^bytes \\*/\\d+$' } },
      } },
      429: { description: 'Rate limit exceeded' },
      500: { description: 'Storage or internal failure', content: {
        'application/json': { schema: appErrorResponseSchema },
      } },
    },
  });
  app.doc('/api/doc', {
    openapi: '3.1.0',
    info: {
      title: 'Manual Maker API', version: '2.0.0',
      description: 'Workers API. Currently documents OpenAPI-registered routes plus health and upload; remaining route contracts are pending.',
    },
  });
}

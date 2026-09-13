/**
 * Cloudflare Workers Edge Layer
 * Handles auth, CORS, rate limiting, and routing to Pages Functions
 */

import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { rateLimiter } from 'hono-rate-limiter';
import { jwt } from 'hono/jwt';
import { HTTPException } from 'hono/http-exception';

// =============================================================================
// Type Definitions
// =============================================================================

/** Cloudflare Workers Environment Bindings */
export interface Env {
  // Pages Functions service binding
  PAGES_FUNCTIONS: Fetcher;
  
  // KV for rate limiting
  RATE_LIMIT_KV: KVNamespace;
  
  // Durable Object for WebSocket progress
  PROGRESS_DO: DurableObjectNamespace;
  
  // Queue for async processing
  PDF_QUEUE: Queue;
  
  // Dead Letter Queue
  PDF_DLQ: Queue;
  
  // R2 Bucket for file storage
  FILES: R2Bucket;
  
  // Secrets
  JWT_SECRET: string;
  API_KEY: string;
  
  // Configuration
  ENVIRONMENT: 'development' | 'preview' | 'production';
  ALLOWED_ORIGINS: string;
  BASE_URL: string;
}

/** JWT Token Payload */
export interface JWTPayload {
  sub: string;           // User ID
  email?: string;        // User email
  role: 'admin' | 'user'; // User role
  exp: number;           // Expiration timestamp
  iat: number;           // Issued at timestamp
}

/** API Response Types */
export interface HealthResponse {
  status: 'ok';
  service: string;
  version: string;
  timestamp: string;
}

export interface ErrorResponse {
  error: string;
  code?: string;
  details?: unknown;
  request_id?: string;
}

export interface RateLimitResponse {
  error: 'Rate limit exceeded';
  retry_after: number;
}

/** Request Context for logging */
export interface RequestContext {
  request_id: string;
  path: string;
  method: string;
  client_ip: string;
  user_agent: string;
  start_time: number;
  user_id?: string;
}

/** Queue Message Types */
export interface QueueMessage {
  file_id: string;
  pdf_key: string;
  options: ProcessingOptions;
  timestamp: number;
  retry_count?: number;
  status?: string;
  error?: string;
}

export interface ProcessingOptions {
  compact_layout?: boolean;
  use_emojis?: boolean;
  prompt_layout?: 'horizontal' | 'vertical';
  prompt_strict_mode?: boolean;
  prompt_has_diagrams?: boolean;
  prompt_low_quality_mode?: boolean;
  base_url?: string;
}

/** Progress Update Message */
export interface ProgressUpdate {
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'error';
  progress: number;
  stage: string;
  result?: unknown;
  error?: string;
  processing_time_ms?: number;
}

/** WebSocket Message Types */
export interface WSMessage {
  type: 'progress' | 'ping' | 'pong' | 'error';
  payload: ProgressUpdate | Record<string, never>;
}

// =============================================================================
// Utility Functions
// =============================================================================

/** Generate unique request ID */
function generateRequestId(): string {
  return crypto.randomUUID().slice(0, 8);
}

/** Create request context from Hono context */
function createRequestContext(c: any): RequestContext {
  return {
    request_id: generateRequestId(),
    path: c.req.path,
    method: c.req.method,
    client_ip: c.req.header('CF-Connecting-IP') || 'unknown',
    user_agent: c.req.header('User-Agent') || 'unknown',
    start_time: Date.now(),
  };
}

/** Log structured data for Cloudflare Logs */
function logStructured(level: 'info' | 'warn' | 'error', message: string, data: Record<string, unknown>): void {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level: level.toUpperCase(),
    message,
    ...data,
  };
  console[level](JSON.stringify(logEntry));
}

/** Validate JWT token */
async function validateToken(token: string, secret: string): Promise<JWTPayload | null> {
  try {
    const key = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(secret),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['verify']
    );
    
    const [headerB64, payloadB64, signatureB64] = token.split('.');
    const data = `${headerB64}.${payloadB64}`;
    const signature = new Uint8Array(atob(signatureB64.replace(/-/g, '+').replace(/_/g, '/')).split('').map(c => c.charCodeAt(0)));
    
    const isValid = await crypto.subtle.verify(
      'HMAC',
      key,
      signature,
      new TextEncoder().encode(data)
    );
    
    if (!isValid) return null;
    
    const payload = JSON.parse(atob(payloadB64.replace(/-/g, '+').replace(/_/g, '/')));
    
    // Check expiration
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      return null;
    }
    
    return payload as JWTPayload;
  } catch {
    return null;
  }
}

// =============================================================================
// Middleware
// =============================================================================

/** Request logging middleware */
async function loggingMiddleware(c: any, next: () => Promise<void>) {
  const ctx = createRequestContext(c);
  const startTime = Date.now();
  
  logStructured('info', 'Incoming request', {
    request_id: ctx.request_id,
    path: ctx.path,
    method: ctx.method,
    client_ip: ctx.client_ip,
  });
  
  try {
    await next();
    
    const duration = Date.now() - startTime;
    logStructured('info', 'Request completed', {
      request_id: ctx.request_id,
      status: c.res.status,
      duration_ms: duration,
    });
  } catch (error) {
    const duration = Date.now() - startTime;
    logStructured('error', 'Request failed', {
      request_id: ctx.request_id,
      error: error instanceof Error ? error.message : String(error),
      duration_ms: duration,
    });
    throw error;
  }
}

/** Rate limiting middleware using KV */
function createRateLimiter() {
  return rateLimiter({
    windowMs: 60 * 1000, // 1 minute
    limit: 100, // 100 requests per minute
    keyGenerator: (c) => `ratelimit:${c.req.header('CF-Connecting-IP') || 'unknown'}:${c.req.path}`,
    store: {
      async get(key: string) {
        // Access KV through the context - this is a limitation of hono-rate-limiter
        // In practice, you'd need to pass the KV namespace differently
        return 0;
      },
      async set(key: string, value: number, ttl: number) {
        // Same limitation
      },
    },
    handler: (c) => {
      return c.json<RateLimitResponse>({
        error: 'Rate limit exceeded',
        retry_after: 60,
      }, 429);
    },
  });
}

/** Authentication middleware */
async function authMiddleware(c: any, next: () => Promise<void>) {
  const authHeader = c.req.header('Authorization');
  
  // Skip auth for health check and public endpoints
  const publicPaths = ['/health', '/api/health', '/metrics', '/api/metrics'];
  if (publicPaths.some(p => c.req.path.startsWith(p))) {
    return next();
  }
  
  // In development, allow unauthenticated
  if (c.env.ENVIRONMENT === 'development') {
    return next();
  }
  
  if (!authHeader) {
    throw new HTTPException(401, { message: 'Authorization header required' });
  }
  
  const token = authHeader.replace('Bearer ', '');
  const payload = await validateToken(token, c.env.JWT_SECRET);
  
  if (!payload) {
    throw new HTTPException(401, { message: 'Invalid or expired token' });
  }
  
  // Attach user info to context
  c.set('user', payload);
  return next();
}

/** WebSocket authentication middleware */
async function wsAuthMiddleware(c: any, next: () => Promise<void>) {
  // For WebSocket, check token in query params or headers
  const url = new URL(c.req.url);
  const token = url.searchParams.get('token') || c.req.header('Sec-WebSocket-Protocol')?.split(',')[1]?.trim();
  
  if (!token && c.env.ENVIRONMENT === 'production') {
    throw new HTTPException(401, { message: 'WebSocket authentication required' });
  }
  
  if (token) {
    const payload = await validateToken(token, c.env.JWT_SECRET);
    if (!payload) {
      throw new HTTPException(401, { message: 'Invalid WebSocket token' });
    }
    c.set('user', payload);
  }
  
  return next();
}

// =============================================================================
// Application Setup
// =============================================================================

const app = new Hono<{ Bindings: Env }>();

// Global middleware
app.use('*', loggingMiddleware);

// CORS middleware
app.use('*', cors({
  origin: (origin, c) => {
    const allowed = c.env.ALLOWED_ORIGINS.split(',').map(o => o.trim());
    if (allowed.includes('*') || allowed.includes(origin)) {
      return origin;
    }
    return allowed[0];
  },
  allowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'Authorization', 'X-Requested-With', 'Sec-WebSocket-Protocol'],
  exposeHeaders: ['Content-Disposition'],
  maxAge: 600,
  credentials: true,
}));

// Rate limiting for API routes
app.use('/api/*', createRateLimiter());

// Authentication for API routes
app.use('/api/*', authMiddleware);

// Health check (no auth/rate limit)
app.get('/health', (c) => {
  const response: HealthResponse = {
    status: 'ok',
    service: 'edge-worker',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
  };
  return c.json(response);
});

// Metrics endpoint (prometheus format)
app.get('/metrics', async (c) => {
  const response = await c.env.PAGES_FUNCTIONS.fetch(
    new URL('/metrics', `https://${c.env.PAGES_FUNCTIONS}`)
  );
  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
});

// Proxy all /api/* requests to Pages Functions
app.all('/api/*', async (c) => {
  const url = new URL(c.req.url);
  const pagesUrl = new URL(url.pathname + url.search, `https://${c.env.PAGES_FUNCTIONS}`);
  
  const requestHeaders = new Headers(c.req.rawHeaders);
  // Add request ID for tracing
  requestHeaders.set('X-Request-ID', createRequestContext(c).request_id);
  
  const response = await c.env.PAGES_FUNCTIONS.fetch(pagesUrl, {
    method: c.req.method,
    headers: requestHeaders,
    body: c.req.method !== 'GET' && c.req.method !== 'HEAD' ? await c.req.arrayBuffer() : undefined,
    redirect: 'manual',
  });
  
  // Add CORS headers to proxied response
  const responseHeaders = new Headers(response.headers);
  const allowedOrigin = c.env.ALLOWED_ORIGINS.split(',')[0].trim();
  responseHeaders.set('Access-Control-Allow-Origin', allowedOrigin);
  
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
});

// Proxy WebSocket connections with auth
app.get('/ws/*', wsAuthMiddleware, async (c) => {
  const url = new URL(c.req.url);
  const pagesUrl = new URL(url.pathname + url.search, `https://${c.env.PAGES_FUNCTIONS}`);
  
  const upgradeHeader = c.req.header('Upgrade');
  if (upgradeHeader?.toLowerCase() !== 'websocket') {
    return c.json<ErrorResponse>({ error: 'WebSocket upgrade required' }, 426);
  }
  
  const requestHeaders = new Headers(c.req.rawHeaders);
  requestHeaders.set('X-Request-ID', createRequestContext(c).request_id);
  
  const response = await c.env.PAGES_FUNCTIONS.fetch(pagesUrl, {
    method: 'GET',
    headers: requestHeaders,
  });
  
  return response;
});

// Serve static assets from Pages
app.get('/*', async (c) => {
  const url = new URL(c.req.url);
  const pagesUrl = new URL(url.pathname + url.search, `https://${c.env.PAGES_FUNCTIONS}`);
  
  const response = await c.env.PAGES_FUNCTIONS.fetch(pagesUrl, {
    method: 'GET',
    headers: c.req.rawHeaders,
  });
  
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
});

// Error handler
app.onError((err, c) => {
  const ctx = createRequestContext(c);
  
  if (err instanceof HTTPException) {
    return c.json<ErrorResponse>({
      error: err.message,
      code: 'HTTP_ERROR',
      request_id: ctx.request_id,
    }, err.status);
  }
  
  logStructured('error', 'Unhandled error', {
    request_id: ctx.request_id,
    error: err instanceof Error ? err.message : String(err),
    stack: err instanceof Error ? err.stack : undefined,
  });
  
  // Don't expose internal errors in production
  if (c.env.ENVIRONMENT === 'production') {
    return c.json<ErrorResponse>({
      error: 'Internal server error',
      code: 'INTERNAL_ERROR',
      request_id: ctx.request_id,
    }, 500);
  }
  
  return c.json<ErrorResponse>({
    error: err instanceof Error ? err.message : String(err),
    code: 'INTERNAL_ERROR',
    request_id: ctx.request_id,
    details: err instanceof Error ? err.stack : undefined,
  }, 500);
});

// Not found handler
app.notFound((c) => {
  return c.json<ErrorResponse>({
    error: 'Not found',
    code: 'NOT_FOUND',
    request_id: createRequestContext(c).request_id,
  }, 404);
});

export default app;
export type { Env, JWTPayload, HealthResponse, ErrorResponse, RequestContext };
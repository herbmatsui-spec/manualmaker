/**
 * Security routes - PII masking (client-offloaded, server provides patterns)
 */
import { OpenAPIHono } from '@hono/zod-openapi';
import type { AppEnv } from '../lib/types';
import { z } from 'zod';
import { AppError } from '../lib/errors';
import { 
  ValidationErrorResponseSchema, 
  InternalErrorResponseSchema 
} from '../lib/openapi-errors';
import { caches } from '../lib/memory-cache';

/** Default PII patterns (regex, label, replacement) - served to client */
const DEFAULT_PII_PATTERNS: Array<{ pattern: string; label: string; replacement: string }> = [
  { pattern: '0\\d{1,4}-\\d{1,4}-\\d{3,4}', label: 'phone', replacement: 'XXX-XXXX-XXXX' },
  { pattern: '[\\w.\\-+]+@[\\w\\-]+\\.[\\w.\\-]+', label: 'email', replacement: 'xxx@example.com' },
  { pattern: '\\d{3}-\\d{4}', label: 'postal', replacement: 'XXX-XXXX' },
  { pattern: '(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})', label: 'credit_card', replacement: 'XXXX-XXXX-XXXX-XXXX' },
  { pattern: '(?:\\d{1,3}\\.){3}\\d{1,3}', label: 'ip_address', replacement: 'XXX.XXX.XXX.XXX' }
];

export function registerSecurityRoutes(app: OpenAPIHono<AppEnv>) {
  /**
   * GET /api/security/status
   */
  app.openapi('/api/security/status',
    'get',
    {
      middleware: [],
      summary: 'Get security status',
      description: 'Returns security feature status and configuration',
      request: {
        params: {
          content: {
            'application/json': {
              schema: z.object({}) // no params
            }
          }
        }
      },
      responses: {
        '200': {
          description: 'Security status',
          content: {
            'application/json': {
              schema: z.object({
                piiMaskingEnabled: z.boolean(),
                piiMaskingTarget: z.string(),
                encryptionAvailable: z.boolean(),
                encryptionKeySet: z.boolean(),
                keyringAvailable: z.boolean(),
                auditLogEnabled: z.boolean()
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
    // @ts-ignore: Overload mismatch
    async (c) => {
      return c.json({
        piiMaskingEnabled: true,
        piiMaskingTarget: 'client',
        encryptionAvailable: false,
        encryptionKeySet: Boolean(c.env.GEMINI_API_KEY),
        keyringAvailable: false,
        auditLogEnabled: false
      });
    });

  /**
   * GET /api/security/patterns
   * Serves PII patterns to the client for client-side masking
   */
  app.openapi('/api/security/patterns',
    'get',
    {
      middleware: [],
      summary: 'Get PII patterns',
      description: 'Serves PII patterns to the client for client-side masking',
      request: {
        params: {
          content: {
            'application/json': {
              schema: z.object({}) // no params
            }
          }
        }
      },
      responses: {
        '200': {
          description: 'PII patterns',
          content: {
            'application/json': {
              schema: z.object({
                patterns: z.array(z.object({
                  pattern: z.string(),
                  label: z.string(),
                  replacement: z.string()
                })),
                source: z.enum(['kv', 'default'])
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
    // @ts-ignore: Overload mismatch
    async (c) => {
      // Try to get from cache
      const cached = caches.piiPatterns.get('pii_patterns');
      if (cached !== undefined) {
        return c.json({ patterns: cached.patterns, source: cached.source });
      }
      try {
        // Try KV for custom patterns, fallback to hardcoded
        let patterns: Array<{pattern: string; label: string; replacement: string}> = [];
        let source: 'kv' | 'default' = 'default';
        if (c.env.PROCESSING_KV) {
          const custom = await c.env.PROCESSING_KV.get('pii_patterns', 'json');
          if (custom && Array.isArray((custom as any).patterns)) {
            patterns = (custom as any).patterns;
            source = 'kv';
          } else {
            patterns = DEFAULT_PII_PATTERNS;
            source = 'default';
          }
        } else {
          patterns = DEFAULT_PII_PATTERNS;
          source = 'default';
        }
        // Save to cache
        caches.piiPatterns.set('pii_patterns', { patterns, source });
        return c.json({ patterns, source });
      } catch (error) {
        const requestId = c.get('requestId') || 'unknown';
        console.error(`[${requestId}] Get patterns error:`, error);
        const patterns = DEFAULT_PII_PATTERNS;
        const source = 'default';
        caches.piiPatterns.set('pii_patterns', { patterns, source });
      }
    });

  /**
   * POST /api/security/mask
   * Server-side masking fallback (light regex work only - safe in 10ms CPU limit)
   */
  app.openapi('/api/security/mask',
    'post',
    {
      middleware: [],
      summary: 'Mask PII in text',
      description: 'Server-side masking fallback (light regex work only - safe in 10ms CPU limit)',
      request: {
        body: {
          content: {
            'application/json': {
              schema: z.object({
                text: z.string().max(1024 * 1024, 'Text too large (max 1MB)')
              })
            }
          }
        }
      },
      responses: {
        '200': {
          description: 'Masked text and counts',
          content: {
            'application/json': {
              schema: z.object({
                maskedText: z.string(),
                counts: z.record(z.number())
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
          description: 'Text too large',
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
    // @ts-ignore: Overload mismatch
    async (c) => {
      const body = await c.req.json();
      const text = typeof body.text === 'string' ? body.text : '';

      if (text.length > 1024 * 1024) {
        throw new AppError('VALIDATION_ERROR', 'Text too large (max 1MB)', 413);
      }

      let maskedText = text;
      const counts: Record<string, number> = {};

      for (const { pattern, label, replacement } of DEFAULT_PII_PATTERNS) {
        const regex = new RegExp(pattern, 'g');
        const matches = maskedText.match(regex);
        if (matches && matches.length > 0) {
          counts[label] = matches.length;
          maskedText = maskedText.replace(regex, replacement);
        }
      }

      return c.json({ maskedText, counts });
    });
}
/**
 * Security routes - PII masking (client-offloaded, server provides patterns)
 */
import { Hono } from 'hono';
import type { Env } from '../lib/types';

/** Default PII patterns (regex, label, replacement) - served to client */
const DEFAULT_PII_PATTERNS: Array<{ pattern: string; label: string; replacement: string }> = [
  { pattern: '0\\d{1,4}-\\d{1,4}-\\d{3,4}', label: 'phone', replacement: 'XXX-XXXX-XXXX' },
  { pattern: '[\\w.\\-+]+@[\\w\\-]+\\.[\\w.\\-]+', label: 'email', replacement: 'xxx@example.com' },
  { pattern: '\\d{3}-\\d{4}', label: 'postal', replacement: 'XXX-XXXX' },
  { pattern: '(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})', label: 'credit_card', replacement: 'XXXX-XXXX-XXXX-XXXX' },
  { pattern: '(?:\\d{1,3}\\.){3}\\d{1,3}', label: 'ip_address', replacement: 'XXX.XXX.XXX.XXX' }
];

export function registerSecurityRoutes(app: Hono<{ Bindings: Env }>) {
  /**
   * GET /api/security/status
   */
  app.get('/api/security/status', (c) => {
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
  app.get('/api/security/patterns', async (c) => {
    try {
      // Try KV for custom patterns, fallback to hardcoded
      if (c.env.PROCESSING_KV) {
        const custom = await c.env.PROCESSING_KV.get('pii_patterns', 'json');
        if (custom && Array.isArray((custom as any).patterns)) {
          return c.json({ patterns: (custom as any).patterns, source: 'kv' });
        }
      }
      return c.json({ patterns: DEFAULT_PII_PATTERNS, source: 'default' });
    } catch (error) {
      console.error('Get patterns error:', error);
      return c.json({ patterns: DEFAULT_PII_PATTERNS, source: 'default' });
    }
  });

  /**
   * POST /api/security/mask
   * Server-side masking fallback (light regex work only - safe in 10ms CPU limit)
   */
  app.post('/api/security/mask', async (c) => {
    try {
      const body = await c.req.json();
      const text = typeof body.text === 'string' ? body.text : '';

      if (text.length > 1024 * 1024) {
        return c.json({ error: 'Text too large (max 1MB)' }, 413);
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
    } catch (error) {
      console.error('Mask error:', error);
      return c.json({ error: 'Masking failed' }, 500);
    }
  });
}

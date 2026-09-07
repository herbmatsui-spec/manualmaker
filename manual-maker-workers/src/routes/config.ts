/**
 * Config routes
 */
import { Hono } from 'hono';
import type { Env, ConfigResponse } from '../lib/types';

export function registerConfigRoutes(app: Hono<{ Bindings: Env }>) {
  app.get('/api/config', (c) => {
    const env = c.env;
    const response: ConfigResponse = {
      geminiModelName: env.GEMINI_MODEL_NAME || 'gemini-1.5-flash',
      processorType: 'cloudflare-workers',
      pdfDpi: 300,
      maxFileSizeMb: parseInt(env.MAX_FILE_SIZE_MB || '50', 10),
      webUploadMaxMb: parseInt(env.WEB_UPLOAD_MAX_MB || '100', 10),
      outputDirectory: 'r2://manual-processor-files',
      supportedExtensions: ['.pdf'],
      defaultLanguage: env.DEFAULT_LANGUAGE || 'ja'
    };
    return c.json(response);
  });
}

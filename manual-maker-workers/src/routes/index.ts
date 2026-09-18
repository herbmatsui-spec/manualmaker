import type { OpenAPIHono } from '@hono/zod-openapi';
import type { AppEnv } from '../lib/types';
import { registerHealthRoutes } from './health';
import { registerConfigRoutes } from './config';
import { registerUploadRoutes } from './upload';
import { registerProcessRoutes } from './process';
import { registerResultsRoutes } from './results';
import { registerDownloadRoutes } from './download';
import { registerGeminiRoutes } from './gemini';
import { registerVisionRoutes } from './vision';
import { registerI18nRoutes } from './i18n';
import { registerSecurityRoutes } from './security';
import { registerMermaidRoutes } from './mermaid';
import { registerOpenAPIRoutes } from './openapi';

/** Shared by the Worker entry point and contract tests. */
export function registerRoutes(app: OpenAPIHono<AppEnv>) {
  registerHealthRoutes(app);
  registerConfigRoutes(app);
  registerUploadRoutes(app);
  registerProcessRoutes(app);
  registerResultsRoutes(app);
  registerDownloadRoutes(app);
  registerGeminiRoutes(app);
  registerVisionRoutes(app);
  registerI18nRoutes(app);
  registerSecurityRoutes(app);
  registerMermaidRoutes(app);
  registerOpenAPIRoutes(app);
}

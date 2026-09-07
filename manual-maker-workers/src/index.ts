import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { etag } from 'hono/etag';
import { logger } from 'hono/logger';
import type { Env } from './lib/types';

const app = new Hono<{ Bindings: Env }>();

app.use('*', cors());
app.use('*', etag());
app.use('*', logger());

// Import and register routes
import { registerHealthRoutes } from './routes/health';
import { registerConfigRoutes } from './routes/config';
import { registerUploadRoutes } from './routes/upload';
import { registerProcessRoutes } from './routes/process';
import { registerResultsRoutes } from './routes/results';
import { registerDownloadRoutes } from './routes/download';
import { registerI18nRoutes } from './routes/i18n';
import { registerSecurityRoutes } from './routes/security';
import { registerMermaidRoutes } from './routes/mermaid';

// Register all routes
registerHealthRoutes(app);
registerConfigRoutes(app);
registerUploadRoutes(app);
registerProcessRoutes(app);
registerResultsRoutes(app);
registerDownloadRoutes(app);
registerI18nRoutes(app);
registerSecurityRoutes(app);
registerMermaidRoutes(app);

// Export for Cloudflare Workers
export default app;
export { app };

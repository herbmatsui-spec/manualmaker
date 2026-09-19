import { createApp } from './app';
import { scheduled } from './scheduled';
import { createGeminiApi } from './lib/external-api';
import { createVisionApi } from './lib/external-api';
import { setApiInstances } from '../lib/routes/metrics';

const app = createApp();
const geminiApi = createGeminiApi(app.env as any);
const visionApi = createVisionApi(app.env as any);
setApiInstances(geminiApi, visionApi);

export default { fetch: app.fetch, scheduled };
export { app };
export { ProgressEngine } from './lib/progress-engine';
export { geminiApi, visionApi };

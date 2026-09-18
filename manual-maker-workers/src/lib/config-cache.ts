import type { Env, ConfigResponse } from '../lib/types';
import { caches } from './memory-cache';

export function getConfig(env: Env): ConfigResponse {
  const cached = caches.config.get<ConfigResponse>('config');
  if (cached) return cached;

  const config: ConfigResponse = {
    geminiModelName: env.GEMINI_MODEL_NAME || 'gemini-1.5-flash',
    processorType: 'cloudflare-workers',
    pdfDpi: 300,
    maxFileSizeMb: parseInt(env.MAX_FILE_SIZE_MB || '50', 10),
    webUploadMaxMb: parseInt(env.WEB_UPLOAD_MAX_MB || '100', 10),
    outputDirectory: 'r2://manual-processor-files',
    supportedExtensions: ['.pdf'],
    defaultLanguage: env.DEFAULT_LANGUAGE || 'ja',
  };

  caches.config.set('config', config);
  return config;
}
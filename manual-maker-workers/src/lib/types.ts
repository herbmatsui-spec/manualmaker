import type { ProgressEngine } from './progress-engine';

export interface Env {
  BUCKET: R2Bucket;
  BUCKET_SECONDARY?: R2Bucket;
  PROCESSING_KV: KVNamespace;
  PROGRESS_DO: DurableObjectNamespace<ProgressEngine>;
  GEMINI_API_KEY: string;
  GOOGLE_API_KEY: string;
  GOOGLE_CLOUD_PROJECT_ID: string;
  // Vars (wrangler.toml [vars])
  DEFAULT_LANGUAGE?: string;
  MAX_FILE_SIZE_MB?: string;
  WEB_UPLOAD_MAX_MB?: string;
  GEMINI_MODEL_NAME?: string;
  RATE_LIMIT_ENABLED?: string;
  RATE_LIMIT_WHITELIST?: string;
}

export interface AppEnv {
  Bindings: Env;
  Variables: {
    requestId: string;
  };
}

export interface UploadedFile {
  fileId: string;
  filename: string;
  sizeMb: number;
  path: string; // R2 key
  uploadedAt: string; // ISO string
}

export interface ProcessingOptions {
  compactLayout?: boolean;
  useEmojis?: boolean;
  promptLayout?: string;
  promptStrictMode?: boolean;
  promptHasDiagrams?: boolean;
  promptLowQualityMode?: boolean;
  baseUrl?: string;
}

export interface ProcessingResult {
  fileId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number; // 0-100
  stage: string;
  result?: {
    markdown?: string;
    html?: string;
    // 他の出力形式はクライアント側で変換
  };
  error?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  processorType: string;
}

export interface ConfigResponse {
  geminiModelName: string;
  processorType: string;
  pdfDpi: number;
  maxFileSizeMb: number;
  webUploadMaxMb: number;
  outputDirectory: string;
  supportedExtensions: string[];
  defaultLanguage: string;
}

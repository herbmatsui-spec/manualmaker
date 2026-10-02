import type { Env } from './types';
import { CircuitBreaker } from './circuit-breaker';
import { fetchWithRetry } from './http-client';
import { ExternalAPIError } from './errors';
import { createFallbackCache } from './fallback-cache';
import type { FallbackCache } from './fallback-cache';
import { apiCacheKey, executeWithApiFallback } from './api-fallback';
import { geminiProxyParams } from './schemas';

interface GeminiRequest {
  contents?: Array<{
    parts: Array<{ text?: string; inlineData?: { data: string; mimeType: string } }>;
  }>;
  generationConfig?: Record<string, unknown>;
  safetySettings?: Array<Record<string, unknown>>;
}

interface VisionRequest {
  requests: Array<{
    image: { content: string };
    features: Array<{ type: string; maxResults?: number }>;
  }>;
}

interface ApiBinding {
  env: Env;
  cache: FallbackCache;
}

/** Request-scoped cache keys prevent sharing one generation across unrelated inputs. */
export class GeminiApi {
  private readonly circuitBreaker = new CircuitBreaker('gemini-api', {
    failureThreshold: 5, recoveryTimeoutMs: 60_000, successThreshold: 3, timeoutMs: 10_000,
  });
  private binding: ApiBinding | undefined;

  constructor(env?: Env) {
    if (env) this.setEnv(env);
  }

  /** Workers env is fixed per deployment; rebinding is what lets one isolate serve differing test envs. */
  setEnv(env: Env): this {
    this.binding = { env, cache: createFallbackCache(env) };
    return this;
  }

  private requireBinding(): ApiBinding {
    if (!this.binding) throw new ExternalAPIError('gemini', 'Gemini API bindings are not configured');
    return this.binding;
  }

  private requireCredential(env: Env): string {
    const credential = env.GEMINI_API_KEY;
    if (!credential) throw new ExternalAPIError('gemini', 'GEMINI_API_KEY is not configured');
    return credential;
  }

  async generateContent(request: GeminiRequest): Promise<any> {
    const { env } = this.requireBinding();
    return this.callModel(env.GEMINI_MODEL_NAME || 'gemini-1.5-flash', 'generateContent', { ...request });
  }

  /** streamGenerateContent deliberately preserves the existing buffered JSON contract. */
  async callModel(modelName: string, methodName: string, request: Record<string, unknown>): Promise<any> {
    const { env, cache } = this.requireBinding();
    const apiKey = this.requireCredential(env);
    const { model, method } = geminiProxyParams.parse({ model: modelName, method: methodName });
    const key = await apiCacheKey('gemini', apiKey, `${model}:${method}`, request);
    return executeWithApiFallback(this.circuitBreaker, cache, key, async signal => {
      const response = await fetchWithRetry(
        `https://generativelanguage.googleapis.com/v1beta/models/${model}:${method}`, {
          method: 'POST', signal,
          headers: { 'Content-Type': 'application/json', 'x-goog-api-key': apiKey },
          body: JSON.stringify(request),
        }, { maxRetries: 2 });
      if (!response.ok) {
        // Do not include provider body (which may echo input) in errors or logs.
        await response.body?.cancel();
        throw new ExternalAPIError('gemini', `Gemini API error: ${response.status}`, response.status);
      }
      return response.json();
    });
  }

  async listModels(): Promise<any> {
    const { env, cache } = this.requireBinding();
    const apiKey = this.requireCredential(env);
    const key = await apiCacheKey('gemini', apiKey, 'listModels', null);
    return executeWithApiFallback(this.circuitBreaker, cache, key, async signal => {
      const response = await fetchWithRetry('https://generativelanguage.googleapis.com/v1beta/models', {
        method: 'GET', signal, headers: { 'x-goog-api-key': apiKey },
      }, { maxRetries: 2 });
      if (!response.ok) {
        await response.body?.cancel();
        throw new ExternalAPIError('gemini', `Gemini API error: ${response.status}`, response.status);
      }
      return response.json();
    });
  }

  getCircuitState() { return this.circuitBreaker.getState(); }
  getCircuitMetrics() { return this.circuitBreaker.getMetrics(); }
  resetCircuitBreaker() { this.circuitBreaker.reset(); }
}

export class VisionApi {
  private readonly circuitBreaker = new CircuitBreaker('vision-api', {
    failureThreshold: 3, recoveryTimeoutMs: 30_000, successThreshold: 2, timeoutMs: 15_000,
  });
  private binding: ApiBinding | undefined;

  constructor(env?: Env) {
    if (env) this.setEnv(env);
  }

  setEnv(env: Env): this {
    this.binding = { env, cache: createFallbackCache(env) };
    return this;
  }

  private requireBinding(): ApiBinding {
    if (!this.binding) throw new ExternalAPIError('vision', 'Vision API bindings are not configured');
    return this.binding;
  }

  async annotateImage(request: VisionRequest): Promise<any> {
    const { env, cache } = this.requireBinding();
    const apiKey = env.GOOGLE_API_KEY;
    if (!apiKey) throw new ExternalAPIError('vision', 'GOOGLE_API_KEY is not configured');
    const key = await apiCacheKey('vision', apiKey, 'annotateImage', request);
    return executeWithApiFallback(this.circuitBreaker, cache, key, async signal => {
      const response = await fetchWithRetry('https://vision.googleapis.com/v1/images:annotate', {
        method: 'POST', signal,
        headers: { 'Content-Type': 'application/json', 'x-goog-api-key': apiKey },
        body: JSON.stringify(request),
      }, { maxRetries: 2 });
      if (!response.ok) {
        await response.body?.cancel();
        throw new ExternalAPIError('vision', `Vision API error: ${response.status}`, response.status);
      }
      return response.json();
    });
  }

  getCircuitState() { return this.circuitBreaker.getState(); }
  getCircuitMetrics() { return this.circuitBreaker.getMetrics(); }
  resetCircuitBreaker() { this.circuitBreaker.reset(); }
}

export function createGeminiApi(env: Env): GeminiApi { return new GeminiApi(env); }
export function createVisionApi(env: Env): VisionApi { return new VisionApi(env); }

let geminiApiInstance: GeminiApi | undefined;
let visionApiInstance: VisionApi | undefined;

/**
 * Per-isolate clients bound to the current request env. Keeping one instance per isolate is what
 * preserves circuit-breaker state across requests; a fresh client per request would reset it.
 */
export function getGeminiApi(env: Env): GeminiApi {
  return (geminiApiInstance ??= new GeminiApi()).setEnv(env);
}

export function getVisionApi(env: Env): VisionApi {
  return (visionApiInstance ??= new VisionApi()).setEnv(env);
}
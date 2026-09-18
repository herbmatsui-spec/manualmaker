import type { Env } from './types';
import { CircuitBreaker } from './circuit-breaker';
import { fetchWithRetry } from './http-client';
import { ExternalAPIError } from './errors';
import { createFallbackCache } from './fallback-cache';
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

/** Request-scoped cache keys prevent sharing one generation across unrelated inputs. */
export class GeminiApi {
  private readonly circuitBreaker = new CircuitBreaker('gemini-api', {
    failureThreshold: 5, recoveryTimeoutMs: 60_000, successThreshold: 3, timeoutMs: 10_000,
  });
  private readonly fallbackCache: ReturnType<typeof createFallbackCache>;

  constructor(private readonly env: Env) {
    this.fallbackCache = createFallbackCache(env);
  }

  async generateContent(request: GeminiRequest): Promise<any> {
    return this.callModel(this.env.GEMINI_MODEL_NAME || 'gemini-1.5-flash', 'generateContent', { ...request });
  }

  /** streamGenerateContent deliberately preserves the existing buffered JSON contract. */
  async callModel(modelName: string, methodName: string, request: Record<string, unknown>): Promise<any> {
    const { model, method } = geminiProxyParams.parse({ model: modelName, method: methodName });
    const key = await apiCacheKey('gemini', this.env.GEMINI_API_KEY, `${model}:${method}`, request);
    return executeWithApiFallback(this.circuitBreaker, this.fallbackCache, key, async signal => {
      const response = await fetchWithRetry(
        `https://generativelanguage.googleapis.com/v1beta/models/${model}:${method}`, {
          method: 'POST', signal,
          headers: { 'Content-Type': 'application/json', 'x-goog-api-key': this.env.GEMINI_API_KEY },
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
    const key = await apiCacheKey('gemini', this.env.GEMINI_API_KEY, 'listModels', null);
    return executeWithApiFallback(this.circuitBreaker, this.fallbackCache, key, async signal => {
      const response = await fetchWithRetry('https://generativelanguage.googleapis.com/v1beta/models', {
        method: 'GET', signal, headers: { 'x-goog-api-key': this.env.GEMINI_API_KEY },
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
  private readonly fallbackCache: ReturnType<typeof createFallbackCache>;

  constructor(private readonly env: Env) {
    this.fallbackCache = createFallbackCache(env);
  }

  async annotateImage(request: VisionRequest): Promise<any> {
    const key = await apiCacheKey('vision', this.env.GOOGLE_API_KEY, 'annotateImage', request);
    return executeWithApiFallback(this.circuitBreaker, this.fallbackCache, key, async signal => {
      const response = await fetchWithRetry('https://vision.googleapis.com/v1/images:annotate', {
        method: 'POST', signal,
        headers: { 'Content-Type': 'application/json', 'x-goog-api-key': this.env.GOOGLE_API_KEY },
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

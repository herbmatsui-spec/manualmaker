import { describe, expect, test, vi, beforeEach, afterEach } from 'vitest';
import type { Env } from '../types';
import { SlidingWindowRateLimiter, createRateLimiter, rateLimitConfigs } from '../rate-limiter';
import { rateLimit, rateLimitUpload, rateLimitGeminiProxy, rateLimitVisionProxy, rateLimitProgressUpdate, rateLimitIPGeneral } from '../rate-limit-middleware';

class MockKVNamespace {
  private store: Map<string, { value: string; expiration: number }> = new Map();
  
  async get(key: string): Promise<string | null> {
    const item = this.store.get(key);
    if (!item || Date.now() > item.expiration) {
      this.store.delete(key);
      return null;
    }
    return item.value;
  }
  
  async put(key: string, value: string, opts: { expirationTtl?: number } = {}): Promise<void> {
    const expiration = Date.now() + (opts.expirationTtl ?? 60) * 1000;
    this.store.set(key, { value, expiration });
  }
  
  async delete(key: string): Promise<void> {
    this.store.delete(key);
  }
  
  async list(options: { prefix?: string; limit?: number } = {}): Promise<{ keys: { name: string }[] }> {
    const prefix = options.prefix ?? '';
    const limit = options.limit ?? 1000;
    const matchingKeys = Array.from(this.store.keys())
      .filter(key => key.startsWith(prefix))
      .slice(0, limit);
    
    return {
      keys: matchingKeys.map(key => ({ name: key }))
    };
  }
}

afterEach(() => {
  vi.useRealTimers();
});

describe('SlidingWindowRateLimiter', () => {
  let kvMock: KVNamespace;
  let limiter: SlidingWindowRateLimiter;
  
  beforeEach(() => {
    kvMock = new MockKVNamespace() as unknown as KVNamespace;
    limiter = new SlidingWindowRateLimiter(kvMock, {
      windowMs: 60000, // 1分
      maxRequests: 5,
      keyPrefix: 'test'
    });
  });
  
  test('should allow requests under limit', async () => {
    for (let i = 0; i < 5; i++) {
      const result = await limiter.consume('test-key');
      expect(result.allowed).toBe(true);
      expect(result.count).toBe(i + 1);
    }
  });
  
  test('should reject requests over limit', async () => {
    // 5回まで許可
    for (let i = 0; i < 5; i++) {
      const result = await limiter.consume('test-key');
      expect(result.allowed).toBe(true);
      expect(result.count).toBe(i + 1);
    }
    
    // 6回目で制限
    const result = await limiter.consume('test-key');
    expect(result.allowed).toBe(false);
    expect(result.count).toBe(6);
    if (result.allowed) throw new Error('Expected a rejected rate-limit result');
    expect(result.retryAfter).toBeGreaterThan(0);
  });
  
  test('should reset after window passes', async () => {
    // 制限までリクエストを送る
    for (let i = 0; i < 5; i++) {
      const result = await limiter.consume('test-key');
      expect(result.allowed).toBe(true);
    }
    
    // 制限超過
    const overLimitResult = await limiter.consume('test-key');
    expect(overLimitResult.allowed).toBe(false);
    
    // 時間を進める（ウィンドウサイズ+10ms）
    vi.useFakeTimers();
    vi.setSystemTime(new Date(Date.now() + 60010));
    
    // 新しいウィンドウでは再度許可されるべき
    const afterWindowResult = await limiter.consume('test-key');
    expect(afterWindowResult.allowed).toBe(true);
    expect(afterWindowResult.count).toBe(1);
    
    vi.useRealTimers();
  });
  
  test('should handle different keys independently', async () => {
    // キーAで制限まで使う
    for (let i = 0; i < 5; i++) {
      const result = await limiter.consume('key-a');
      expect(result.allowed).toBe(true);
    }
    
    // キーBはまだ使えるべき
    const resultB = await limiter.consume('key-b');
    expect(resultB.allowed).toBe(true);
    expect(resultB.count).toBe(1);
    
    // キーAはまだ制限中
    const resultA = await limiter.consume('key-a');
    expect(resultA.allowed).toBe(false);
  });
  
  test('should respect whitelist', async () => {
    const whitelist = new Set(['whitelisted-key']);
    const limiterWithWhitelist = new SlidingWindowRateLimiter(kvMock, {
      windowMs: 60000,
      maxRequests: 1,
      keyPrefix: 'test',
      whitelist
    });
    
    // ホワイトリストキーは制限なく何度でも使える
    for (let i = 0; i < 10; i++) {
      const result = await limiterWithWhitelist.consume('whitelisted-key');
      expect(result.allowed).toBe(true);
      expect(result.count).toBe(0); // ホワイトリストの場合はカウントは0
    }
    
    // ホワイトリスト外のキーは通常通り制限される
    const resultNormal = await limiterWithWhitelist.consume('normal-key');
    expect(resultNormal.allowed).toBe(true);
    expect(resultNormal.count).toBe(1);
    
    const resultOver = await limiterWithWhitelist.consume('normal-key');
    expect(resultOver.allowed).toBe(false);
  });
});

describe('rateLimitConfigs', () => {
  test('should have all required configurations', () => {
    expect(rateLimitConfigs.upload).toBeDefined();
    expect(rateLimitConfigs.geminiProxy).toBeDefined();
    expect(rateLimitConfigs.visionProxy).toBeDefined();
    expect(rateLimitConfigs.progressUpdate).toBeDefined();
    expect(rateLimitConfigs.ipGeneral).toBeDefined();
    
    // 値の妥当性をチェック
    expect(rateLimitConfigs.upload.maxRequests).toBe(10);
    expect(rateLimitConfigs.upload.windowMs).toBe(60 * 1000);
    
    expect(rateLimitConfigs.geminiProxy.maxRequests).toBe(30);
    expect(rateLimitConfigs.geminiProxy.windowMs).toBe(60 * 1000);
    
    expect(rateLimitConfigs.visionProxy.maxRequests).toBe(20);
    expect(rateLimitConfigs.visionProxy.windowMs).toBe(60 * 1000);
    
    expect(rateLimitConfigs.progressUpdate.maxRequests).toBe(6);
    expect(rateLimitConfigs.progressUpdate.windowMs).toBe(10 * 1000);
    
    expect(rateLimitConfigs.ipGeneral.maxRequests).toBe(150);
    expect(rateLimitConfigs.ipGeneral.windowMs).toBe(60 * 1000);
  });
});

describe('createRateLimiter', () => {
  test('should create limiter with correct dependencies', () => {
    const mockEnv: Env = {
      BUCKET: {} as any,
      PROCESSING_KV: new MockKVNamespace() as unknown as KVNamespace,
      GEMINI_API_KEY: 'test-key',
      GOOGLE_API_KEY: 'test-key',
      GOOGLE_CLOUD_PROJECT_ID: 'test-project',
      PROGRESS_DO: {} as any,
      DEFAULT_LANGUAGE: 'ja',
      MAX_FILE_SIZE_MB: '50',
      WEB_UPLOAD_MAX_MB: '100',
      GEMINI_MODEL_NAME: 'gemini-1.5-flash'
    } as unknown as Env;
    
    const limiter = createRateLimiter(mockEnv, rateLimitConfigs.upload);
    expect(limiter).toBeInstanceOf(SlidingWindowRateLimiter);
  });
});

describe('rateLimit middleware', () => {
  let kvMock: KVNamespace;
  let env: Env;
  
  beforeEach(() => {
    kvMock = new MockKVNamespace() as unknown as KVNamespace;
    env = {
      BUCKET: {} as any,
      PROCESSING_KV: kvMock,
      GEMINI_API_KEY: 'test-key',
      GOOGLE_API_KEY: 'test-key',
      GOOGLE_CLOUD_PROJECT_ID: 'test-project',
      PROGRESS_DO: {} as any,
      DEFAULT_LANGUAGE: 'ja',
      MAX_FILE_SIZE_MB: '50',
      WEB_UPLOAD_MAX_MB: '100',
      GEMINI_MODEL_NAME: 'gemini-1.5-flash',
      RATE_LIMIT_ENABLED: undefined, // enable by default
    } as unknown as Env;
  });
  
const createMockContext = (path: string, ip?: string) => {
  const c = {
    req: {
      header: (name: string) => ip ?? '127.0.0.1',
      path: path,
    },
    env,
    res: {
      headers: new Headers(),
    },
    get: (key: string) => {
      if (key === 'requestId') return 'test-request-id';
      return undefined;
    },
    json: (body: any, status: number = 200) => {
      return new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  } as any;
  return c;
};
  
  const mockNext = async () => { };
  
  test('should set headers on allowed request', async () => {
    const limiter = rateLimit('upload', {});
    const c = createMockContext('/api/upload');
    
    await limiter(c, mockNext);
    
    expect(c.res.headers.has('RateLimit-Limit')).toBe(true);
    expect(c.res.headers.get('RateLimit-Limit')).toBe('10'); // from upload config
    expect(c.res.headers.has('RateLimit-Remaining')).toBe(true);
    // Remaining should be maxRequests - 1 = 9
    expect(c.res.headers.get('RateLimit-Remaining')).toBe('9');
    expect(c.res.headers.has('RateLimit-Reset')).toBe(true);
    // Reset timestamp should be a number
    const reset = c.res.headers.get('RateLimit-Reset');
    expect(reset).not.toBeNull();
    const resetNum = parseInt(reset, 10);
    expect(resetNum).toBeGreaterThan(Date.now());
  });
  
  test('should return 429 and set headers on blocked request', async () => {
    const limiter = rateLimit('upload', {});
    const c = createMockContext('/api/upload');

    // First, consume all allowed requests
    for (let i = 0; i < 10; i++) {
      await limiter(c, mockNext);
    }

    // The next request should be blocked
    const res = await limiter(c, mockNext);
    expect(res).not.toBeUndefined();
    if (!res) throw new Error('Expected a rate-limit response');
    expect(res.status).toBe(429);
    expect(await res.json()).toEqual({ error: 'Too many requests', retryAfter: expect.any(Number) });
    
    // Check headers
    expect(c.res.headers.has('Retry-After')).toBe(true);
    const retryAfter = parseInt(c.res.headers.get('Retry-After') || '0', 10);
    expect(retryAfter).toBeGreaterThan(0);
    expect(c.res.headers.has('RateLimit-Limit')).toBe(true);
    expect(c.res.headers.get('RateLimit-Limit')).toBe('10');
    expect(c.res.headers.has('RateLimit-Remaining')).toBe(true);
    expect(c.res.headers.get('RateLimit-Remaining')).toBe('0');
    expect(c.res.headers.has('RateLimit-Reset')).toBe(true);
  });
  
  test('should respect whitelist from environment variable', async () => {
    // Set the whitelist environment variable
    env.RATE_LIMIT_WHITELIST = '127.0.0.1,::1';
    const limiter = rateLimitIPGeneral({}); // uses ipGeneral config
    const c = createMockContext('/api/test', '127.0.0.1');
    
    // Even if we exceed the limit, it should be allowed due to whitelist
    for (let i = 0; i < 200; i++) {
      const res = await limiter(c, mockNext);
      expect(res).toBeUndefined(); // middleware calls next and returns undefined
    }
  });
  
  test('should skip rate limit when RATE_LIMIT_ENABLED=false', async () => {
    env.RATE_LIMIT_ENABLED = 'false';
    const limiter = rateLimitIPGeneral({});
    const c = createMockContext('/api/test');
    
    // Even if we exceed the limit, it should be allowed
    for (let i = 0; i < 200; i++) {
      const res = await limiter(c, mockNext);
      expect(res).toBeUndefined();
    }
  });
});
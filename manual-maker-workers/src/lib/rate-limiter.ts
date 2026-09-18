import type { Env } from '../lib/types';
import { RateLimitError } from '../lib/errors';

export interface RateLimitConfig {
  windowMs: number; // タイムウィンドウサイズ（ミリ秒）
  maxRequests: number; // ウィンドウ内最大リクエスト数
  keyPrefix: string; // KVキーのプレフィックス
  whitelist?: Set<string>; // 制限を除外するキーの集合
}

export interface RateLimitResult {
  allowed: true;
  count: number;
  resetAt: number; // epoch ms
}

export interface RateLimitExceeded {
  allowed: false;
  retryAfter: number; // seconds
  count: number;
  resetAt: number; // epoch ms
}

export class SlidingWindowRateLimiter {
  constructor(
    private readonly kv: KVNamespace,
    private readonly config: RateLimitConfig
  ) {}

  /**
   * リクエストが制限内かチェックし、現在のカウントをインクリメント
   * @param key 識別キー（IPアドレスやfileIdなど）
   */
async consume(key: string): Promise<RateLimitResult | RateLimitExceeded> {
     // ホワイトリストチェック
     if (this.config.whitelist?.has(key)) {
       return { allowed: true, count: 0, resetAt: Date.now() + this.config.windowMs };
     }

     const now = Date.now();
     const windowDuration = this.config.windowMs;
     const windowIndex = Math.floor(now / windowDuration);
     const kvKey = `${this.config.keyPrefix}:${key}:${windowIndex}`;
     const blockedKey = `${this.config.keyPrefix}:${key}:${windowIndex}:blocked`;

     // 現在のウィンドウのカウントを取得
     const current = await this.kv.get(kvKey);
     const count = current ? parseInt(current, 10) + 1 : 1;

     // ブロックカウントを取得（ブロックされている場合のみインクリメント）
     let blockedIncrement = 0;
     if (count > this.config.maxRequests) {
       blockedIncrement = 1;
     }

     // 総リクエストカウントを保存
     await this.kv.put(kvKey, String(count), {
       expirationTtl: Math.max(60, Math.ceil(windowDuration / 1000) + 10),
     });

     // ブロックカウントを保存（ある場合のみ）
     if (blockedIncrement > 0) {
       const blockedCurrent = await this.kv.get(blockedKey);
       const blockedCount = blockedCurrent ? parseInt(blockedCurrent, 10) + blockedIncrement : blockedIncrement;
       await this.kv.put(blockedKey, String(blockedCount), {
         expirationTtl: Math.max(60, Math.ceil(windowDuration / 1000) + 10),
       });
     }

     const resetAt = (windowIndex + 1) * windowDuration;

     if (count > this.config.maxRequests) {
       const retryAfter = Math.max(1, Math.ceil((resetAt - now) / 1000));
       return { allowed: false, retryAfter, count, resetAt };
     }

     return { allowed: true, count, resetAt };
   }
}

/**
 * ファクトリ関数
 */
export function createRateLimiter(
  env: Env,
  config: RateLimitConfig
): SlidingWindowRateLimiter {
  const whitelist = new Set(config.whitelist);
  if (config.keyPrefix === rateLimitConfigs.ipGeneral.keyPrefix) {
    for (const key of (env.RATE_LIMIT_WHITELIST ?? '').split(',').map(s => s.trim()).filter(Boolean)) {
      whitelist.add(key);
    }
  }
  return new SlidingWindowRateLimiter(env.PROCESSING_KV, { ...config, whitelist });
}

/**
 * 事前定義されたレートリミッター設定
 */
export const rateLimitConfigs = {
  upload: {
    windowMs: 60 * 1000, // 1分
    maxRequests: 10, // 1分間に10回
    keyPrefix: 'ratelimit:upload',
  },
  geminiProxy: {
    windowMs: 60 * 1000, // 1分
    maxRequests: 30, // 1分間に30回（Gemini APIの無料枠考慮）
    keyPrefix: 'ratelimit:gemini',
  },
  visionProxy: {
    windowMs: 60 * 1000, // 1分
    maxRequests: 20, // 1分間に20回（Vision APIの無料枠考慮）
    keyPrefix: 'ratelimit:vision',
  },
  progressUpdate: {
    windowMs: 10 * 1000, // 10秒
    maxRequests: 6, // 10秒間に6回（1秒に1回程度に制限）
    keyPrefix: 'ratelimit:progress',
  },
ipGeneral: {
     windowMs: 60 * 1000, // 1分
     maxRequests: 150, // 1分間に150回（一般的なAPI保護）
     keyPrefix: 'ratelimit:ip',
     whitelist: new Set<string>(),
   },
};
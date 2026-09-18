import type { Env } from './types';

export class FailoverManager {
  private isPrimaryHealthy: boolean | null = null;
  private isSecondaryHealthy: boolean | null = null;
  private kvHealthy: boolean | null = null;
  private lastCheckedAt: string | null = null;
  private pending: Promise<void> | undefined;

  constructor(private readonly env: Env, private readonly timeoutMs = 5000) {}

  private async probe(operation: () => Promise<unknown>): Promise<boolean> {
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      await Promise.race([
        Promise.resolve().then(operation),
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Health probe timeout')), this.timeoutMs); }),
      ]);
      return true;
    } catch { return false; }
    finally { clearTimeout(timer); }
  }

  /** Read-only availability checks: no claim about replica freshness or write access. */
  async checkR2Health(): Promise<{ primary: boolean; secondary: boolean }> {
    const [primary, secondary] = await Promise.all([
      this.probe(() => this.env.BUCKET.list({ prefix: '_health/', limit: 1 })),
      this.env.BUCKET_SECONDARY
        ? this.probe(() => this.env.BUCKET_SECONDARY!.list({ prefix: '_health/', limit: 1 }))
        : Promise.resolve(false),
    ]);
    this.isPrimaryHealthy = primary;
    this.isSecondaryHealthy = secondary;
    return { primary, secondary };
  }

  async checkKVHealth(): Promise<{ primary: boolean }> {
    const primary = await this.probe(() => this.env.PROCESSING_KV.list({ prefix: '_health/', limit: 1 }));
    this.kvHealthy = primary;
    return { primary };
  }

  /** Coalesce concurrent monitoring requests and cache only a short-lived snapshot. */
  async refresh(): Promise<void> {
    if (this.pending) return this.pending;
    if (this.lastCheckedAt && Date.now() - Date.parse(this.lastCheckedAt) < 30_000) return;
    this.pending = (async () => {
      await Promise.all([this.checkR2Health(), this.checkKVHealth()]);
      this.lastCheckedAt = new Date().toISOString();
    })();
    try { await this.pending; } finally { this.pending = undefined; }
  }

  getStatus() {
    return {
      primaryR2Healthy: this.isPrimaryHealthy,
      secondaryR2Healthy: this.isSecondaryHealthy,
      secondaryConfigured: Boolean(this.env.BUCKET_SECONDARY),
      primaryKVHealthy: this.kvHealthy,
      lastCheckedAt: this.lastCheckedAt,
      failoverInProgress: false,
      failoverMode: 'manual' as const,
      failoverRecommended: this.isPrimaryHealthy === false && this.isSecondaryHealthy === true,
      replicaConsistency: 'unverified' as const,
    };
  }

  async attemptFailover(): Promise<boolean> {
    // Replica verification and an operator-approved binding change are required.
    return false;
  }

  getActiveR2Bucket(): R2Bucket {
    // All production routes still use BUCKET. Never report a fictitious switch.
    return this.env.BUCKET;
  }
}

const managers = new WeakMap<Env, FailoverManager>();
export function createFailoverManager(env: Env) {
  let manager = managers.get(env);
  if (!manager) { manager = new FailoverManager(env); managers.set(env, manager); }
  return manager;
}

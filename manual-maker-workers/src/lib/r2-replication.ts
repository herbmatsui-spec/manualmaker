import type { Env } from './types';

/** Best-effort replica, not a strongly consistent mirror. */
export class R2Replication {
  constructor(
    private readonly primary: R2Bucket,
    private readonly secondary?: R2Bucket,
    private readonly enabled = true,
  ) {}

  async replicateObject(key: string): Promise<void> {
    if (!this.enabled || !this.secondary) return;
    const object = await this.primary.get(key);
    if (!object) throw new Error('Replication source is missing');
    try {
      const stored = await this.secondary.put(key, object.body, {
        httpMetadata: object.httpMetadata,
        customMetadata: object.customMetadata,
      });
      if (!stored) throw new Error('Replication write was not committed');
    } finally {
      // Failed writes may leave an unread, unlocked stream behind.
      if (!object.body.locked) {
        await object.body.cancel().catch(() => {});
      }
    }
  }

  async replicateDeletion(key: string): Promise<void> {
    if (!this.enabled || !this.secondary) return;
    await this.secondary.delete(key);
  }

  /** Administrative repair: copy differing objects; never delete unknown replicas. */
  async syncBucket(): Promise<{ replicated: number; failed: number }> {
    if (!this.enabled || !this.secondary) return { replicated: 0, failed: 0 };
    let replicated = 0;
    let failed = 0;
    let cursor: string | undefined;
    do {
      // Listing failure rejects: a partial scan must not be reported as complete.
      const page = await this.primary.list({ cursor, limit: 1000 });
      for (const object of page.objects) {
        try {
          const replica = await this.secondary.head(object.key);
          if (replica && replica.etag === object.etag) continue;
          await this.replicateObject(object.key);
          replicated++;
        } catch {
          failed++;
        }
      }
      const next = page.truncated ? page.cursor : undefined;
      if (page.truncated && (!next || next === cursor)) {
        throw new Error('Replication listing did not advance');
      }
      cursor = next;
    } while (cursor);
    return { replicated, failed };
  }
}

export function createR2Replication(env: Env): R2Replication {
  return new R2Replication(env.BUCKET, env.BUCKET_SECONDARY);
}

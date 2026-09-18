import { z } from 'zod';
import type { Env } from './types';

const entrySchema = z.object({
  key: z.string().min(1).max(512),
  object: z.string(),
  sha256: z.string().regex(/^[a-f0-9]{64}$/),
  size: z.number().int().nonnegative().max(25 * 1024 * 1024),
  metadata: z.unknown().optional(),
  expiration: z.number().int().positive().optional(),
});
const manifestSchema = z.object({
  version: z.literal(1), id: z.string().uuid(), complete: z.literal(true),
  createdAt: z.string().datetime(), entries: z.array(entrySchema).max(100),
});
const digest = async (value: ArrayBuffer) => Array.from(
  new Uint8Array(await crypto.subtle.digest('SHA-256', value)),
  byte => byte.toString(16).padStart(2, '0'),
).join('');

/** Bounded, non-atomic KV export. Larger namespaces need a resumable Queue workflow. */
export class KVReplication {
  constructor(
    private readonly kv: KVNamespace,
    private readonly bucket: R2Bucket,
    private readonly backupPrefix = 'kv-backups/',
  ) {}

  async backup() {
    const backupId = crypto.randomUUID();
    const prefix = `${this.backupPrefix}${backupId}/`;
    const entries: z.infer<typeof entrySchema>[] = [];
    let totalCount = 0;
    let bytes = 0;
    try {
      let cursor: string | undefined;
      let pages = 0;
      do {
        if (++pages > 100) throw new Error('Backup page limit exceeded');
        const page = await this.kv.list({ cursor, limit: 100 });
        totalCount += page.keys.length;
        if (totalCount > 100) throw new Error('Backup key limit exceeded (100)');
        for (const key of page.keys) {
          const record = await this.kv.getWithMetadata(key.name, 'arrayBuffer');
          if (record.value === null) throw new Error('KV changed during backup; retry required');
          bytes += record.value.byteLength;
          if (bytes > 50 * 1024 * 1024) throw new Error('Backup size limit exceeded (50MiB)');
          const entry = entrySchema.parse({
            key: key.name, object: `${prefix}${entries.length}.bin`,
            size: record.value.byteLength, sha256: await digest(record.value),
            metadata: record.metadata, expiration: key.expiration,
          });
          const stored = await this.bucket.put(entry.object, record.value, {
            httpMetadata: { contentType: 'application/octet-stream' },
          });
          if (!stored) throw new Error('Backup value write not committed');
          entries.push(entry);
        }
        const next = page.list_complete ? undefined : page.cursor;
        if (!page.list_complete && (!next || next === cursor)) throw new Error('KV listing did not advance');
        cursor = next;
      } while (cursor);
      const manifest = manifestSchema.parse({
        version: 1, id: backupId, complete: true, createdAt: new Date().toISOString(), entries,
      });
      // Publishing this marker last prevents partial exports being restored.
      const stored = await this.bucket.put(`${prefix}manifest.json`, JSON.stringify(manifest), {
        httpMetadata: { contentType: 'application/json' },
      });
      if (!stored) throw new Error('Backup manifest write not committed');
      return { success: true, backupId, backedUpCount: entries.length, totalCount };
    } catch (error) {
      return { success: false, backupId, backedUpCount: entries.length, totalCount,
        error: error instanceof Error ? error.message : String(error) };
    }
  }

  /** Dry-run by default. Explicit apply restores to this instance's KV; no deletions. */
  async restoreFromBackup(backupId: string, options: { apply?: boolean } = {}) {
    let restoredCount = 0;
    let skippedCount = 0;
    try {
      z.string().uuid().parse(backupId);
      const prefix = `${this.backupPrefix}${backupId}/`;
      const object = await this.bucket.get(`${prefix}manifest.json`);
      if (!object) throw new Error('Complete backup manifest not found');
      if (object.size > 1024 * 1024) {
        await object.body.cancel();
        throw new Error('Backup manifest too large');
      }
      const manifest = manifestSchema.parse(await object.json());
      if (manifest.id !== backupId) throw new Error('Backup identity mismatch');
      const keys = new Set<string>();
      let totalBytes = 0;
      for (const [index, entry] of manifest.entries.entries()) {
        if (entry.object !== `${prefix}${index}.bin` || keys.has(entry.key)) {
          throw new Error('Invalid backup entry identity');
        }
        keys.add(entry.key);
        totalBytes += entry.size;
      }
      if (totalBytes > 50 * 1024 * 1024) throw new Error('Backup exceeds restore size limit');
      const readEntry = async (entry: z.infer<typeof entrySchema>) => {
        const stored = await this.bucket.get(entry.object);
        if (!stored) throw new Error('Backup value missing');
        if (stored.size !== entry.size) {
          await stored.body.cancel();
          throw new Error('Backup value size mismatch');
        }
        const value = await stored.arrayBuffer();
        if (value.byteLength !== entry.size || await digest(value) !== entry.sha256) {
          throw new Error('Backup checksum mismatch');
        }
        return value;
      };
      // Validate every object before the first KV write; retain at most one value.
      for (const entry of manifest.entries) await readEntry(entry);
      for (const entry of manifest.entries) {
        // KV requires expiration at least 60 seconds in the future.
        if (entry.expiration !== undefined && entry.expiration <= Math.floor(Date.now() / 1000) + 60) {
          skippedCount++;
          continue;
        }
        if (options.apply) {
          const value = await readEntry(entry);
          await this.kv.put(entry.key, value, {
            ...(entry.expiration === undefined ? {} : { expiration: entry.expiration }),
            ...(entry.metadata == null ? {} : { metadata: entry.metadata }),
          });
          restoredCount++;
        }
      }
      return { success: true, dryRun: !options.apply, validatedCount: manifest.entries.length, restoredCount, skippedCount };
    } catch (error) {
      // Restore is not transactional: report writes already completed.
      return { success: false, dryRun: !options.apply, restoredCount, skippedCount,
        error: error instanceof Error ? error.message : String(error) };
    }
  }
}

export function createKVReplication(env: Env) {
  return new KVReplication(env.PROCESSING_KV, env.BUCKET_SECONDARY ?? env.BUCKET);
}

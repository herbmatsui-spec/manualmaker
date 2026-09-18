import type { Env } from './lib/types';
import { createKVReplication } from './lib/kv-replication';

/** Reject failures so Workers scheduled-event monitoring records them. */
export async function runScheduledBackup(env: Env): Promise<void> {
  const result = await createKVReplication(env).backup();
  const summary = {
    event: 'kv_backup_completed', success: result.success,
    backupId: result.backupId, backedUpCount: result.backedUpCount,
    totalCount: result.totalCount,
  };
  if (!result.success) {
    console.error(JSON.stringify({ ...summary, event: 'kv_backup_failed' }));
    throw new Error('Scheduled KV backup failed');
  }
  console.info(JSON.stringify(summary));
}

export function scheduled(
  _event: ScheduledController,
  env: Env,
  context: Pick<ExecutionContext, 'waitUntil'>,
): void {
  context.waitUntil(runScheduledBackup(env));
}

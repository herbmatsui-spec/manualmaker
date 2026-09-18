import { afterEach, describe, expect, it, vi } from 'vitest';
import { scheduled } from '../../scheduled';
import type { Env } from '../types';

afterEach(() => vi.restoreAllMocks());

describe('P7-4 scheduled backup', () => {
  it.each([false, true])('tracks the backup and reports storage failure=%s', async failure => {
    const info = vi.spyOn(console, 'info').mockImplementation(() => {});
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    const put = vi.fn(async () => {
      if (failure) throw new Error('private storage failure');
      return {};
    });
    const primaryPut = vi.fn();
    const env = {
      PROCESSING_KV: { list: async () => ({ keys: [], list_complete: true }) },
      BUCKET: { put: primaryPut }, BUCKET_SECONDARY: { put },
    } as unknown as Env;
    let task!: Promise<unknown>;
    const waitUntil = vi.fn((pending: Promise<unknown>) => { task = pending; });
    scheduled({} as ScheduledController, env, { waitUntil });
    expect(waitUntil).toHaveBeenCalledTimes(1);
    if (failure) {
      await expect(task).rejects.toThrow('Scheduled KV backup failed');
      expect(error).toHaveBeenCalledWith(expect.stringContaining('kv_backup_failed'));
      expect(info).not.toHaveBeenCalled();
    } else {
      await expect(task).resolves.toBeUndefined();
      expect(info).toHaveBeenCalledWith(expect.stringContaining('kv_backup_completed'));
      expect(error).not.toHaveBeenCalled();
    }
    expect(put).toHaveBeenCalledTimes(1);
    expect(primaryPut).not.toHaveBeenCalled();
  });
});

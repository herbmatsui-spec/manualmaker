import { describe, it, expect, vi } from 'vitest';
import { KVReplication } from '../kv-replication';

function setup() {
  const records = new Map<string, { value: ArrayBuffer; metadata: unknown; expiration?: number }>([
    ['process:a/b_日本語', { value: new Uint8Array([0, 255, 128, 1]).buffer, metadata: { source: 'test' } }],
    ['process:a_b_日本語', { value: new ArrayBuffer(0), metadata: null }],
  ]);
  const objects = new Map<string, Blob>();
  const list = vi.fn(async (_options?: unknown) => ({
    keys: Array.from(records, ([name, record]) => ({ name, expiration: record.expiration })), list_complete: true,
  }));
  const getWithMetadata = vi.fn(async (key: string) => records.get(key) ?? { value: null, metadata: null });
  const kvPut = vi.fn(async (_key: string, _value: ArrayBuffer, _options?: unknown) => {});
  const put = vi.fn(async (key: string, value: string | ArrayBuffer) => {
    objects.set(key, new Blob([value])); return { key };
  });
  const get = vi.fn(async (key: string) => {
    const blob = objects.get(key);
    return blob ? { size: blob.size, body: blob.stream(), json: async () => JSON.parse(await blob.text()),
      arrayBuffer: () => blob.arrayBuffer() } : null;
  });
  const replication = new KVReplication(
    { list, getWithMetadata, put: kvPut } as unknown as KVNamespace,
    { get, put } as unknown as R2Bucket,
  );
  return { replication, records, objects, list, getWithMetadata, kvPut, put, get };
}

describe('P7-3 KV backup and restore', () => {
  it('round trips exact keys, binary and empty values, metadata and expiration', async () => {
    const s = setup();
    const expiration = Math.floor(Date.now() / 1000) + 3600;
    s.records.get('process:a/b_日本語')!.expiration = expiration;
    const backup = await s.replication.backup();
    expect(backup).toMatchObject({ success: true, backedUpCount: 2, totalCount: 2 });
    expect(s.put.mock.calls.at(-1)![0]).toBe(`kv-backups/${backup.backupId}/manifest.json`);
    expect(await s.replication.restoreFromBackup(backup.backupId)).toMatchObject({
      success: true, dryRun: true, validatedCount: 2, restoredCount: 0,
    });
    expect(s.kvPut).not.toHaveBeenCalled();
    expect(await s.replication.restoreFromBackup(backup.backupId, { apply: true })).toMatchObject({
      success: true, dryRun: false, restoredCount: 2,
    });
    expect(s.kvPut).toHaveBeenCalledWith('process:a/b_日本語', new Uint8Array([0, 255, 128, 1]).buffer,
      { metadata: { source: 'test' }, expiration });
    expect(s.kvPut).toHaveBeenCalledWith('process:a_b_日本語', new ArrayBuffer(0), {});
  });

  it('never publishes a complete manifest after partial write failure', async () => {
    const s = setup();
    const original = s.put.getMockImplementation()!;
    s.put.mockImplementation(async (key, value) => {
      if (key.endsWith('/1.bin')) throw new Error('unavailable');
      return original(key, value);
    });
    const backup = await s.replication.backup();
    expect(backup).toMatchObject({ success: false, backedUpCount: 1, totalCount: 2 });
    expect(s.objects.has(`kv-backups/${backup.backupId}/manifest.json`)).toBe(false);
    expect(await s.replication.restoreFromBackup(backup.backupId, { apply: true })).toMatchObject({ success: false });
    expect(s.kvPut).not.toHaveBeenCalled();
  });

  it('detects same-size corruption before any restore write', async () => {
    const s = setup(); const backup = await s.replication.backup();
    s.objects.set(`kv-backups/${backup.backupId}/0.bin`, new Blob([new Uint8Array([1, 2, 3, 4])]));
    expect(await s.replication.restoreFromBackup(backup.backupId, { apply: true })).toMatchObject({
      success: false, restoredCount: 0, error: 'Backup checksum mismatch',
    });
    expect(s.kvPut).not.toHaveBeenCalled();
  });

  it('does not resurrect expired keys', async () => {
    const s = setup();
    s.records.get('process:a/b_日本語')!.expiration = Math.floor(Date.now() / 1000) - 1;
    const backup = await s.replication.backup();
    expect(await s.replication.restoreFromBackup(backup.backupId, { apply: true })).toMatchObject({
      success: true, restoredCount: 1, skippedCount: 1,
    });
    expect(s.kvPut).toHaveBeenCalledTimes(1);
  });

  it('reports partial restore writes rather than false success', async () => {
    const s = setup(); const backup = await s.replication.backup();
    s.kvPut.mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error('KV unavailable'));
    expect(await s.replication.restoreFromBackup(backup.backupId, { apply: true })).toMatchObject({
      success: false, restoredCount: 1, error: 'KV unavailable',
    });
  });

  it('follows KV pagination and keeps one backup identity', async () => {
    const s = setup();
    const keys = [...s.records.keys()];
    s.list.mockResolvedValueOnce({ keys: [{ name: keys[0] }], list_complete: false, cursor: 'page2' } as never)
      .mockResolvedValueOnce({ keys: [{ name: keys[1] }], list_complete: true } as never);
    expect(await s.replication.backup()).toMatchObject({ success: true, backedUpCount: 2 });
    expect(s.list).toHaveBeenLastCalledWith({ cursor: 'page2', limit: 100 });
  });

  it('fails safely when the bounded export limit is exceeded', async () => {
    const s = setup();
    s.list.mockResolvedValue({ keys: Array.from({ length: 101 }, (_, i) => ({ name: String(i) })), list_complete: true } as never);
    expect(await s.replication.backup()).toMatchObject({ success: false, backedUpCount: 0 });
    expect(s.put).not.toHaveBeenCalled();
  });

  it('rejects changed KV keys and invalid backup identifiers', async () => {
    const s = setup(); s.getWithMetadata.mockResolvedValue({ value: null, metadata: null });
    expect(await s.replication.backup()).toMatchObject({ success: false });
    expect(await s.replication.restoreFromBackup('../other', { apply: true })).toMatchObject({ success: false });
    expect(s.get).not.toHaveBeenCalled();
    expect(s.kvPut).not.toHaveBeenCalled();
  });
});

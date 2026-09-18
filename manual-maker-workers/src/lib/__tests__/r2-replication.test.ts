import { describe, it, expect, vi } from 'vitest';
import { R2Replication } from '../r2-replication';

function setup() {
  const cancel = vi.fn();
  const body = new ReadableStream<Uint8Array>({ cancel });
  const object = { body, httpMetadata: { contentType: 'application/pdf' }, customMetadata: { source: 'upload' } };
  const get = vi.fn().mockResolvedValue(object);
  const list = vi.fn().mockResolvedValue({ objects: [{ key: 'a', etag: 'new' }], truncated: false });
  const put = vi.fn().mockResolvedValue({ etag: 'new' });
  const head = vi.fn().mockResolvedValue(null);
  const remove = vi.fn().mockResolvedValue(undefined);
  const primary = { get, list } as unknown as R2Bucket;
  const secondary = { put, head, delete: remove } as unknown as R2Bucket;
  return { replication: new R2Replication(primary, secondary), primary, get, list, put, head, remove, body, object, cancel };
}

describe('P7 R2 replication', () => {
  it('passes the original body and both metadata types', async () => {
    const s = setup();
    await s.replication.replicateObject('a');
    expect(s.get).toHaveBeenCalledExactlyOnceWith('a');
    expect(s.put).toHaveBeenCalledExactlyOnceWith('a', s.body, {
      httpMetadata: s.object.httpMetadata, customMetadata: s.object.customMetadata,
    });
  });
  it('rejects missing sources without writing a replica', async () => {
    const s = setup(); s.get.mockResolvedValue(null);
    await expect(s.replication.replicateObject('a')).rejects.toThrow('source is missing');
    expect(s.put).not.toHaveBeenCalled();
  });
  it('preserves write failures and cancels unread source', async () => {
    const s = setup(); const error = new Error('unavailable');
    s.put.mockRejectedValue(error);
    await expect(s.replication.replicateObject('a')).rejects.toBe(error);
    expect(s.cancel).toHaveBeenCalledTimes(1);
  });
  it('rejects uncommitted writes', async () => {
    const s = setup(); s.put.mockResolvedValue(null);
    await expect(s.replication.replicateObject('a')).rejects.toThrow('not committed');
  });
  it('does no work without a secondary', async () => {
    const s = setup(); const replication = new R2Replication(s.primary);
    await replication.replicateObject('a');
    await replication.replicateDeletion('a');
    expect(await replication.syncBucket()).toEqual({ replicated: 0, failed: 0 });
    expect(s.get).not.toHaveBeenCalled(); expect(s.list).not.toHaveBeenCalled();
  });
  it('counts failed copies rather than reporting success', async () => {
    const s = setup(); s.put.mockRejectedValue(new Error('unavailable'));
    expect(await s.replication.syncBucket()).toEqual({ replicated: 0, failed: 1 });
  });
  it('repairs differing replicas and skips matching etags', async () => {
    const s = setup();
    s.list.mockResolvedValue({ objects: [{ key: 'same', etag: 'old' }, { key: 'changed', etag: 'new' }], truncated: false });
    s.head.mockResolvedValue({ etag: 'old' });
    expect(await s.replication.syncBucket()).toEqual({ replicated: 1, failed: 0 });
    expect(s.get).toHaveBeenCalledExactlyOnceWith('changed');
  });
  it('rejects incomplete scans', async () => {
    const s = setup(); s.list.mockRejectedValue(new Error('list failed'));
    await expect(s.replication.syncBucket()).rejects.toThrow('list failed');
  });
  it('follows pagination without rereading matching object bodies', async () => {
    const s = setup();
    s.list.mockResolvedValueOnce({ objects: [{ key: 'a', etag: 'same' }], truncated: true, cursor: 'next' })
      .mockResolvedValueOnce({ objects: [{ key: 'b', etag: 'same' }], truncated: false });
    s.head.mockResolvedValue({ etag: 'same' });
    expect(await s.replication.syncBucket()).toEqual({ replicated: 0, failed: 0 });
    expect(s.list).toHaveBeenLastCalledWith({ cursor: 'next', limit: 1000 });
    expect(s.get).not.toHaveBeenCalled();
  });
  it('rejects a non-advancing truncated listing', async () => {
    const s = setup();
    s.list.mockResolvedValue({ objects: [], truncated: true, cursor: 'same' });
    await expect(s.replication.syncBucket()).rejects.toThrow('did not advance');
    expect(s.list).toHaveBeenCalledTimes(2);
  });
  it('replicates deletions and exposes deletion failures', async () => {
    const s = setup(); await s.replication.replicateDeletion('a');
    expect(s.remove).toHaveBeenCalledWith('a');
    s.remove.mockRejectedValue(new Error('delete failed'));
    await expect(s.replication.replicateDeletion('a')).rejects.toThrow('delete failed');
  });
});

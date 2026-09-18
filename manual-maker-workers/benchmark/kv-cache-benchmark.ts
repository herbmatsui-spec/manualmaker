import { UploadedFile } from '../lib/types';
import { createKVBatch } from '../lib/kv-batch';

/**
 * Mock KV namespace that counts get operations.
 */
class MockKV implements KVNamespace {
  private store: Map<string, string> = new Map();
  private getCount = 0;
  private listCount = 0;

  constructor(initialData: Record<string, string> = {}) {
    for (const [key, value] of Object.entries(initialData)) {
      this.store.set(key, value);
    }
  }

  async get<T = unknown>(key: string, type: 'text' | 'json' | 'arrayBuffer' | 'stream'): Promise<T | null> {
    this.getCount++;
    if (type === 'json') {
      const value = this.store.get(key);
      return value ? JSON.parse(value) : null;
    }
    // For simplicity, we only handle json in this benchmark
    return null as unknown as T;
  }

  async list(options: { prefix?: string; limit?: number; cursor?: string }): Promise<{ keys: { name: string; expiration?: string | null }[]; list_complete: boolean; cursor: string | null }> {
    this.listCount++;
    const prefix = options.prefix ?? '';
    const limit = options.limit ?? 1000;
    const keys: { name: string; expiration?: string | null }[] = [];
    for (const [key] of this.store) {
      if (key.startsWith(prefix)) {
        keys.push({ name: key, expiration: null });
        if (keys.length >= limit) break;
      }
    }
    return {
      keys,
      list_complete: keys.length < this.store.size,
      cursor: null
    };
  }

  // We don't need other methods for this benchmark
  async put(key: string, value: string | Blob | ArrayBuffer, options?: { expirationTtl?: number; expiration?: number; metadata?: unknown; }): Promise<void> {
    if (typeof value === 'string') {
      this.store.set(key, value);
    } else {
      // Simplify: convert to string
      this.store.set(key, value.toString());
    }
    return Promise.resolve();
  }

  async delete(key: string): Promise<void> {
    this.store.delete(key);
    return Promise.resolve();
  }

  getCounts() {
    return { getCount: this.getCount, listCount: this.listCount };
  }
}

/**
 * Simulate the old way of fetching uploads list (list + individual gets)
 */
async function getUploadsOldWay(kv: KVNamespace): Promise<UploadedFile[]> {
  const list = await kv.list({ prefix: 'uploaded:' });
  const uploads: UploadedFile[] = [];
  for (const key of list.keys) {
    const data = await kv.get(key.name, 'json');
    if (data) {
      uploads.push(data as UploadedFile);
    }
  }
  return uploads;
}

/**
 * Simulate the new way using KV batch getByPrefix
 */
async function getUploadsNewWay(kv: KVNamespace): Promise<UploadedFile[]> {
  const kvBatch = createKVBatch({ PROCESSING_KV: kv } as any); // mock env
  const records = await kvBatch.getByPrefix<UploadedFile>('uploaded:');
  return Object.values(records);
}

/**
 * Run a benchmark simulating multiple requests to /api/uploads
 */
async function runBenchmark() {
  const ITERATIONS = 100; // simulate 100 requests
  
  // Prepare mock data: 50 uploaded files
  const mockData: Record<string, string> = {};
  for (let i = 1; i <= 50; i++) {
    const file: UploadedFile = {
      fileId: `file-${i}`,
      filename: `document${i}.pdf`,
      sizeMb: 1.5,
      path: `uploads/${file.fileId}/document${i}.pdf`,
      uploadedAt: new Date().toISOString()
    };
    mockData[`uploaded:${file.fileId}`] = JSON.stringify(file);
  }

  console.log('=== KV Cache Benchmark for /api/uploads ===');
  console.log(`Mock data: ${Object.keys(mockData).length} uploaded files`);
  console.log(`Simulating ${ITERATIONS} requests\n`);

  // Old way
  const kvOld = new MockKV(mockData);
  const startOld = Date.now();
  for (let i = 0; i < ITERATIONS; i++) {
    await getUploadsOldWay(kvOld);
  }
  const endOld = Date.now();
  const oldCounts = kvOld.getCounts();

  // New way
  const kvNew = new MockKV(mockData);
  const startNew = Date.now();
  for (let i = 0; i < ITERATIONS; i++) {
    await getUploadsNewWay(kvNew);
  }
  const endNew = Date.now();
  const newCounts = kvNew.getCounts();

  console.log('Results:');
  console.log(`  Old way (list + individual gets):`);
  console.log(`    Time: ${endOld - startOld}ms`);
  console.log(`    KV list operations: ${oldCounts.listCount}`);
  console.log(`    KV get operations: ${oldCounts.getCount}`);
  console.log(`    Total KV operations: ${oldCounts.listCount + oldCounts.getCount}`);
  console.log(`  New way (KV batch getByPrefix):`);
  console.log(`    Time: ${endNew - startNew}ms`);
  console.log(`    KV list operations: ${newCounts.listCount}`);
  console.log(`    KV get operations: ${newCounts.getCount}`);
  console.log(`    Total KV operations: ${newCounts.listCount + newCounts.getCount}`);

  const oldTotalOps = oldCounts.listCount + oldCounts.getCount;
  const newTotalOps = newCounts.listCount + newCounts.getCount;
  if (oldTotalOps > 0) {
    const reduction = ((oldTotalOps - newTotalOps) / oldTotalOps) * 100;
    console.log(`\nKV operation reduction: ${reduction.toFixed(2)}%`);
  }

  // Also simulate cache hit rate for i18n and piiPatterns? Not required for this benchmark but we can mention.
  console.log('\nNote: This benchmark focuses on the uploads list endpoint.');
  console.log('For i18n and PII pattern caches, hit rates would depend on request patterns.');
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runBenchmark().catch(console.error);
}

export { getUploadsOldWay, getUploadsNewWay, MockKV };
import { it, expect } from 'vitest';
import { measureStreamSize, streamToArrayBuffer } from '../src/lib/stream-utils';

const MiB = 1024 * 1024;

// Local synthetic comparison, not an HTTP/R2 benchmark or historical baseline.
it('compares buffered and streamed consumption at 50/100 MiB and concurrency 1/4', async () => {
  const results = [];
  for (const sizeMiB of [50, 100]) {
    for (const concurrency of [1, 4]) {
      for (const mode of ['stream', 'buffer'] as const) {
        const baseline = process.memoryUsage();
        let peakHeap = baseline.heapUsed;
        let peakBuffers = baseline.arrayBuffers;
        let peakRss = baseline.rss;
        const sample = () => {
          const memory = process.memoryUsage();
          peakHeap = Math.max(peakHeap, memory.heapUsed);
          peakBuffers = Math.max(peakBuffers, memory.arrayBuffers);
          peakRss = Math.max(peakRss, memory.rss);
        };
        const start = performance.now();
        await Promise.all(Array.from({ length: concurrency }, async () => {
          let remaining = sizeMiB * MiB;
          const source = new ReadableStream<Uint8Array>({
            pull(controller) {
              if (!remaining) { controller.close(); return; }
              const length = Math.min(64 * 1024, remaining);
              controller.enqueue(new Uint8Array(length).fill(1));
              remaining -= length;
              sample();
            },
          }, { highWaterMark: 0 });
          if (mode === 'buffer') {
            const buffer = await streamToArrayBuffer(source, sizeMiB * MiB);
            sample();
            expect(buffer.byteLength).toBe(sizeMiB * MiB);
          } else {
            const measured = measureStreamSize(source, sizeMiB * MiB);
            let consumed = 0;
            await measured.stream.pipeTo(new WritableStream<Uint8Array>({
              write(chunk) { consumed += chunk.byteLength; sample(); },
            }));
            expect(consumed).toBe(sizeMiB * MiB);
            expect(await measured.size).toBe(consumed);
          }
        }));
        results.push({
          sizeMiB, concurrency, mode,
          elapsedMs: Math.round(performance.now() - start),
          heapDeltaMiB: +((peakHeap - baseline.heapUsed) / MiB).toFixed(2),
          arrayBufferDeltaMiB: +((peakBuffers - baseline.arrayBuffers) / MiB).toFixed(2),
          rssDeltaMiB: +((peakRss - baseline.rss) / MiB).toFixed(2),
        });
      }
    }
  }
  console.log(JSON.stringify({ node: process.version, platform: process.platform, results }, null, 2));
}, 120_000);

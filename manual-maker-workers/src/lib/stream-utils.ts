export async function streamToArrayBuffer(
  stream: ReadableStream<Uint8Array>,
  maxSize: number
): Promise<ArrayBuffer> {
  if (!Number.isSafeInteger(maxSize) || maxSize < 0) {
    throw new RangeError('maxSize must be a non-negative safe integer');
  }
  const chunks: Uint8Array[] = [];
  let size = 0;

  const reader = stream.getReader();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      size += value.byteLength;
      if (size > maxSize) {
        throw new Error(`Stream too large (max ${maxSize} bytes)`);
      }

      chunks.push(value);
    }
  } catch (error) {
    try { await reader.cancel(error); } catch { /* Preserve the original failure. */ }
    throw error;
  } finally {
    reader.releaseLock();
  }

  const result = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result.buffer;
}

/** Consume the returned stream before awaiting size; no pre-buffering is performed. */
export function measureStreamSize(
  source: ReadableStream<Uint8Array>,
  maxSize = Number.MAX_SAFE_INTEGER
): { size: Promise<number>; stream: ReadableStream<Uint8Array> } {
  if (!Number.isSafeInteger(maxSize) || maxSize < 0) {
    throw new RangeError('maxSize must be a non-negative safe integer');
  }
  const reader = source.getReader();
  let total = 0;
  let finished = false;
  let resolveSize!: (value: number) => void;
  let rejectSize!: (reason: unknown) => void;
  const size = new Promise<number>((resolve, reject) => {
    resolveSize = resolve;
    rejectSize = reject;
  });
  // Consumers may observe the stream failure before they await the size promise.
  void size.catch(() => {});
  const stream = new ReadableStream<Uint8Array>({
    async pull(controller) {
      try {
        const { done, value } = await reader.read();
        if (finished) return;
        if (done) {
          finished = true;
          reader.releaseLock();
          resolveSize(total);
          controller.close();
          return;
        }
        total += value.byteLength;
        if (total > maxSize) throw new Error(`Stream too large (max ${maxSize} bytes)`);
        controller.enqueue(value);
      } catch (error) {
        if (finished) return;
        finished = true;
        rejectSize(error);
        controller.error(error);
        try { await reader.cancel(error); } catch { /* Preserve the original failure. */ }
        reader.releaseLock();
      }
    },
    async cancel(reason) {
      if (finished) return;
      finished = true;
      rejectSize(reason ?? new Error('Stream cancelled before measurement completed'));
      try { await reader.cancel(reason); } finally { reader.releaseLock(); }
    },
  }, { highWaterMark: 0 });
  return { size, stream };
}

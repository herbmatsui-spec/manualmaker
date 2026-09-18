import { describe, it, expect, vi } from 'vitest';
import { streamToArrayBuffer, measureStreamSize } from '../stream-utils';

describe('stream-utils', () => {
  it('measures 100 MiB incrementally without retaining the payload', async () => {
    const total = 100 * 1024 * 1024;
    let produced = 0;
    const source = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (produced === total) { controller.close(); return; }
        const chunk = new Uint8Array(64 * 1024);
        produced += chunk.byteLength;
        controller.enqueue(chunk);
      },
    }, { highWaterMark: 0 });
    const measured = measureStreamSize(source, total);
    let consumed = 0;
    await measured.stream.pipeTo(new WritableStream<Uint8Array>({
      write(chunk) { consumed += chunk.byteLength; },
    }));
    expect(consumed).toBe(total);
    expect(await measured.size).toBe(total);
    expect(source.locked).toBe(false);
  });
  it('does not drain a slow source ahead of consumer demand', async () => {
    let pulls = 0;
    const cancel = vi.fn();
    const source = new ReadableStream<Uint8Array>({
      pull(controller) { pulls++; controller.enqueue(new Uint8Array(65536)); },
      cancel,
    }, { highWaterMark: 0 });
    const measured = measureStreamSize(source);
    await new Promise(resolve => setTimeout(resolve, 10));
    expect(pulls).toBe(0);
    const reader = measured.stream.getReader();
    await reader.read();
    await new Promise(resolve => setTimeout(resolve, 10));
    expect(pulls).toBe(1);
    await reader.cancel('stop');
    reader.releaseLock();
    await expect(measured.size).rejects.toBe('stop');
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(source.locked).toBe(false);
  });

  it('cancels safely while an upstream read is pending', async () => {
    const cancel = vi.fn();
    const source = new ReadableStream<Uint8Array>({ cancel });
    const measured = measureStreamSize(source);
    const reader = measured.stream.getReader();
    const pending = reader.read();
    await reader.cancel('disconnect');
    expect(await pending).toEqual({ done: true, value: undefined });
    await expect(measured.size).rejects.toBe('disconnect');
    reader.releaseLock();
    expect(source.locked).toBe(false);
    expect(cancel).toHaveBeenCalledTimes(1);
  });
  it.each(['buffer', 'measure'])('cancels upstream on %s size overflow, preserving original error', async (mode) => {
    const cancel = vi.fn(() => { throw new Error('cleanup failure'); });
    const source = new ReadableStream<Uint8Array>({
      pull(controller) { controller.enqueue(new Uint8Array(10)); },
      cancel,
    });
    if (mode === 'buffer') {
      await expect(streamToArrayBuffer(source, 5)).rejects.toThrow('Stream too large');
    } else {
      const measured = measureStreamSize(source, 5);
      await expect(streamToArrayBuffer(measured.stream, 100)).rejects.toThrow('Stream too large');
      await expect(measured.size).rejects.toThrow('Stream too large');
    }
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(source.locked).toBe(false);
  });

  it('propagates downstream cancellation and rejects incomplete measurement', async () => {
    const cancel = vi.fn();
    const source = new ReadableStream<Uint8Array>({ cancel });
    const measured = measureStreamSize(source);
    await measured.stream.cancel('client disconnected');
    expect(cancel).toHaveBeenCalledWith('client disconnected');
    await expect(measured.size).rejects.toBe('client disconnected');
    expect(source.locked).toBe(false);
  });

  it.each([-1, NaN, Infinity, 1.5])('rejects invalid limit %s without locking source', async (limit) => {
    const source = new ReadableStream<Uint8Array>();
    expect(() => measureStreamSize(source, limit)).toThrow(RangeError);
    await expect(streamToArrayBuffer(source, limit)).rejects.toThrow(RangeError);
    expect(source.locked).toBe(false);
  });
  describe('streamToArrayBuffer', () => {
    it('should convert a stream to ArrayBuffer', async () => {
      const data = new TextEncoder().encode('hello world');
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(data);
          controller.close();
        }
      });

      const result = await streamToArrayBuffer(stream, 1024);
      expect(new Uint8Array(result)).toEqual(data);
    });

    it('should throw if stream exceeds maxSize', async () => {
      const data = new TextEncoder().encode('hello world');
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(data);
          controller.close();
        }
      });

      await expect(streamToArrayBuffer(stream, 5)).rejects.toThrow('Stream too large');
    });

    it('should release reader lock on error', async () => {
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new Uint8Array([1, 2, 3]));
          controller.error(new Error('test error'));
        }
      });

      await expect(streamToArrayBuffer(stream, 10)).rejects.toThrow('test error');
    });
  });

  describe('measureStreamSize', () => {
    it('should measure stream size and return readable stream', async () => {
      const data = new TextEncoder().encode('hello world');
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(data);
          controller.close();
        }
      });

      const { size, stream: resultStream } = measureStreamSize(stream);
      const result = await streamToArrayBuffer(resultStream, 1024);
      expect(await size).toBe(11);
      expect(new Uint8Array(result)).toEqual(data);
    });

    it('should handle empty stream', async () => {
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.close();
        }
      });

      const { size, stream: resultStream } = measureStreamSize(stream);
      await streamToArrayBuffer(resultStream, 1024);
      expect(await size).toBe(0);
      expect(resultStream).toBeInstanceOf(ReadableStream);
    });

    it('should handle multiple chunks', async () => {
      const chunk1 = new TextEncoder().encode('hello ');
      const chunk2 = new TextEncoder().encode('world');
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(chunk1);
          controller.enqueue(chunk2);
          controller.close();
        }
      });

      const { size, stream: resultStream } = measureStreamSize(stream);
      const result = await streamToArrayBuffer(resultStream, 1024);
      expect(await size).toBe(11);
      expect(new Uint8Array(result)).toEqual(new Uint8Array([...chunk1, ...chunk2]));
    });

    it('should release reader lock on error', async () => {
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new Uint8Array([1, 2, 3]));
          controller.error(new Error('stream error'));
        }
      });

      const measured = measureStreamSize(stream);
      await expect(streamToArrayBuffer(measured.stream, 1024)).rejects.toThrow('stream error');
      await expect(measured.size).rejects.toThrow('stream error');
      expect(stream.locked).toBe(false);
    });
  });
});
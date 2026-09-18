import { DurableObject } from 'cloudflare:workers';
import type { Env } from './types';
import { createMetricsTracker } from './progress-metrics';

export interface ProcessingState {
  fileId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number; // 0-100
  stage: string;
  result?: {
    markdown?: string;
    html?: string;
  };
  error?: string;
  updatedAt?: string; // ISO timestamp
}

export class ProgressEngine extends DurableObject<Env> {
  private state: ProcessingState | null = null;
  private readonly webSockets: Set<WebSocket> = new Set();
  private readonly metricsTracker = createMetricsTracker();

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.ctx.blockConcurrencyWhile(async () => {
      const stored = await this.ctx.storage.get<ProcessingState>('state');
      if (stored) this.state = stored;
    });
  }

  private async saveMetricsToKV() {
    try {
      const fileId = this.ctx.id.toString();
      const metrics = this.metricsTracker.getMetrics();
      await this.env.PROCESSING_KV.put(
        `progress-metrics:${fileId}`,
        JSON.stringify({ ...metrics, fileId, timestamp: new Date().toISOString() }),
        { expirationTtl: 60 * 60 } // 1 hour TTL
      );
    } catch (e) {
      console.warn('Failed to save progress metrics to KV:', e);
    }
  }

  async fetch(request: Request): Promise<Response> {
    if (request.headers.get('upgrade') !== 'websocket') {
      return new Response('Expected WebSocket', { status: 426 });
    }

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);

    server.accept();
    this.webSockets.add(server);
    this.metricsTracker.recordConnection();
    await this.saveMetricsToKV();

    if (this.state) {
      const message = JSON.stringify(this.state);
      server.send(message);
      // Record outgoing message to this connection
      this.metricsTracker.recordUpdate(message.length);
      await this.saveMetricsToKV();
    }

    server.addEventListener('message', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
      } catch (e) {
        console.warn('Invalid WebSocket message:', e);
      }
    });

    server.addEventListener('close', () => {
      this.webSockets.delete(server);
      this.metricsTracker.recordDisconnect();
      this.ctx.waitUntil(this.saveMetricsToKV());
    });

    return new Response(null, { status: 101, webSocket: client });
  }

  async updateProgress(state: ProcessingState) {
    this.state = state;
    this.state.updatedAt = new Date().toISOString();

    try {
      await this.ctx.storage.put('state', this.state);
    } catch (e) {
      console.warn('Failed to backup progress to storage:', e);
    }

    const message = JSON.stringify(this.state);
    for (const ws of this.webSockets) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(message);
        this.metricsTracker.recordUpdate(message.length);
      }
    }
    await this.saveMetricsToKV();
  }

  async queryProgress(): Promise<ProcessingState | null> {
    return this.state;
  }

  async clear() {
    this.state = null;
    await this.ctx.storage.delete('state');
    
    const message = JSON.stringify(null);
    for (const ws of this.webSockets) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(message);
        this.metricsTracker.recordUpdate(message.length);
      }
    }
    await this.saveMetricsToKV();
  }

  getMetrics() {
    return this.metricsTracker.getMetrics();
  }
}

interface WebSocketPair {
  0: WebSocket;
  1: WebSocket;
}
declare const WebSocketPair: {
  new (): WebSocketPair;
  prototype: WebSocketPair;
};
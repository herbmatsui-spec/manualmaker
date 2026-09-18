/**
 * Progress metrics for Durable Objects monitoring
 */

export interface ProgressMetrics {
  activeConnections: number;
  totalUpdates: number;
  broadcastBytes: number;
}

export function createProgressMetrics(): ProgressMetrics {
  return {
    activeConnections: 0,
    totalUpdates: 0,
    broadcastBytes: 0,
  };
}

export interface ProgressMetricsTracker {
  metrics: ProgressMetrics;
  recordUpdate(messageSize: number): void;
  recordConnection(): void;
  recordDisconnect(): void;
  getMetrics(): ProgressMetrics;
}

export function createMetricsTracker(): ProgressMetricsTracker {
  const metrics = createProgressMetrics();

  return {
    metrics,
    recordUpdate(messageSize: number) {
      this.metrics.totalUpdates++;
      this.metrics.broadcastBytes += messageSize * 2; // UTF-16近似
    },
    recordConnection() {
      this.metrics.activeConnections++;
    },
    recordDisconnect() {
      this.metrics.activeConnections = Math.max(0, this.metrics.activeConnections - 1);
    },
    getMetrics(): ProgressMetrics {
      return { ...this.metrics };
    },
  };
}
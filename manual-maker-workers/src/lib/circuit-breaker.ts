export enum CircuitState {
  CLOSED = 'closed',
  OPEN = 'open',
  HALF_OPEN = 'half_open',
}

export interface CircuitBreakerOptions {
  failureThreshold: number;
  recoveryTimeoutMs: number;
  successThreshold: number;
  timeoutMs?: number;
  onOpen?: () => Promise<unknown> | unknown;
}

export class CircuitBreakerOpenError extends Error {
  constructor(
    public readonly circuitName: string,
    public readonly retryAfterSeconds: number
  ) {
    super(`CircuitBreaker ${circuitName} is OPEN. Retry after ${retryAfterSeconds} seconds`);
    this.name = 'CircuitBreakerOpenError';
  }
}

export class CircuitBreaker<T = unknown> {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount = 0;
  private successCount = 0;
  private lastFailureTime: number | null = null;
  private readonly timeoutMs: number;
  private recoveryProbe: symbol | null = null;
  private generation = 0;

  constructor(
    public readonly name: string,
    private readonly options: CircuitBreakerOptions
  ) {
    this.timeoutMs = options.timeoutMs ?? 5000;
  }

  async execute<R>(operation: (signal: AbortSignal) => Promise<R>): Promise<R> {
    if (this.state === CircuitState.OPEN) {
      if (this.shouldAttemptReset()) {
        this.state = CircuitState.HALF_OPEN;
        this.generation++;
        console.info(`CircuitBreaker ${this.name}: HALF_OPEN (attempting reset)`);
      } else {
        throw new CircuitBreakerOpenError(this.name, this.getTimeUntilReset());
      }
    }

    let probe: symbol | null = null;
    if (this.state === CircuitState.HALF_OPEN) {
      if (this.recoveryProbe !== null) {
        throw new CircuitBreakerOpenError(this.name, 1);
      }
      probe = Symbol('recovery-probe');
      this.recoveryProbe = probe;
    }

    const generation = this.generation;
    let result: R;
    try {
      result = await this.executeWithTimeout(operation);
      if (generation === this.generation) this.onSuccess();
      return result;
    } catch (error) {
      if (generation === this.generation && this.onFailure()) {
        try {
          const fallback = await this.options.onOpen?.();
          if (fallback !== undefined) {
            return fallback as unknown as R;
          }
        } catch (fallbackError) {
          console.error(`CircuitBreaker ${this.name}: fallback also failed:`, fallbackError);
        }
      }

      throw error;
    } finally {
      if (probe !== null && this.recoveryProbe === probe) {
        this.recoveryProbe = null;
      }
    }
  }

  private shouldAttemptReset(): boolean {
    if (this.lastFailureTime === null) return false;
    return Date.now() - this.lastFailureTime >= this.options.recoveryTimeoutMs;
  }

  private getTimeUntilReset(): number {
    if (this.lastFailureTime === null) return 0;
    const elapsed = Date.now() - this.lastFailureTime;
    const remaining = this.options.recoveryTimeoutMs - elapsed;
    return Math.max(0, Math.ceil(remaining / 1000));
  }

  private async executeWithTimeout<R>(operation: (signal: AbortSignal) => Promise<R>): Promise<R> {
    const controller = new AbortController();
    if (this.options.timeoutMs === undefined) {
      return await operation(controller.signal);
    }

    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([
        Promise.resolve().then(() => operation(controller.signal)),
        new Promise<R>((_, reject) => {
          timer = setTimeout(
            () => {
              const error = new Error(`Operation timeout after ${this.options.timeoutMs}ms`);
              reject(error);
              controller.abort(error);
            },
            this.options.timeoutMs
          );
        }),
      ]);
    } finally {
      clearTimeout(timer);
    }
  }

  private onSuccess(): void {
    this.failureCount = 0;
    if (this.state === CircuitState.HALF_OPEN) {
      this.successCount++;
      if (this.successCount >= this.options.successThreshold) {
        this.state = CircuitState.CLOSED;
        this.generation++;
        this.successCount = 0;
        console.info(`CircuitBreaker ${this.name}: CLOSED (recovered)`);
      }
    }
  }

  private onFailure(): boolean {
    this.failureCount++;
    this.lastFailureTime = Date.now();

    if (this.state === CircuitState.HALF_OPEN) {
      this.state = CircuitState.OPEN;
      this.generation++;
      this.successCount = 0;
      console.warn(`CircuitBreaker ${this.name}: OPEN (failure during half-open)`);
      return true;
    }
    if (this.state === CircuitState.CLOSED && this.failureCount >= this.options.failureThreshold) {
      this.state = CircuitState.OPEN;
      this.generation++;
      console.warn(`CircuitBreaker ${this.name}: OPEN (failure threshold reached)`);
      return true;
    }
    return false;
  }

  getState(): CircuitState {
    return this.state;
  }

  reset(): void {
    this.generation++;
    this.state = CircuitState.CLOSED;
    this.failureCount = 0;
    this.successCount = 0;
    this.lastFailureTime = null;
    this.recoveryProbe = null;
    console.info(`CircuitBreaker ${this.name}: manually reset to CLOSED`);
  }

  getMetrics(): {
    state: CircuitState;
    failureCount: number;
    successCount: number;
    lastFailureTime: number | null;
    name: string;
  } {
    return {
      state: this.state,
      failureCount: this.failureCount,
      successCount: this.successCount,
      lastFailureTime: this.lastFailureTime,
      name: this.name,
    };
  }
}

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { CircuitBreaker, CircuitState, CircuitBreakerOpenError } from '../circuit-breaker';

describe('CircuitBreaker', () => {
  let cb: CircuitBreaker<any>;
  
  afterEach(() => {
    vi.useRealTimers();
  });

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'));
    cb = new CircuitBreaker('test', {
      failureThreshold: 3,
      recoveryTimeoutMs: 100, // Short timeout for testing
      successThreshold: 2,
    });
  });

  it('should start in CLOSED state', () => {
    expect(cb.getState()).toBe(CircuitState.CLOSED);
  });

  it('should remain CLOSED when under failure threshold', async () => {
    const failingOperation = () => Promise.reject(new Error('Failed'));
    
    // 2 failures (below threshold of 3)
    for (let i = 0; i < 2; i++) {
      try {
        await cb.execute(failingOperation);
      } catch (e) {
        // Expected to fail
      }
    }
    
    expect(cb.getState()).toBe(CircuitState.CLOSED);
  });

  it('should transition to OPEN after failure threshold', async () => {
    const failingOperation = () => Promise.reject(new Error('Failed'));
    
    // 3 failures (reaches threshold of 3)
    for (let i = 0; i < 3; i++) {
      try {
        await cb.execute(failingOperation);
      } catch (e) {
        // Expected to fail
      }
    }
    
    expect(cb.getState()).toBe(CircuitState.OPEN);
  });

  it('should throw CircuitBreakerOpenError when OPEN', async () => {
    const failingOperation = () => Promise.reject(new Error('Failed'));
    
    // Trip the circuit breaker
    for (let i = 0; i < 3; i++) {
      try {
        await cb.execute(failingOperation);
      } catch (e) {
        // Expected to fail
      }
    }
    
    // Should throw CircuitBreakerOpenError
    await expect(cb.execute(() => Promise.resolve('success')))
      .rejects
      .toThrow(CircuitBreakerOpenError);
  });

  it('should transition from OPEN to HALF_OPEN after recovery timeout', async () => {
    const failingOperation = () => Promise.reject(new Error('Failed'));
    const succeedingOperation = () => Promise.resolve('success');
    
    // Trip the circuit breaker
    for (let i = 0; i < 3; i++) {
      try {
        await cb.execute(failingOperation);
      } catch (e) {
        // Expected to fail
      }
    }
    
    expect(cb.getState()).toBe(CircuitState.OPEN);
    
    // Wait for recovery timeout (100ms)
    vi.advanceTimersByTime(110);
    
    // Next attempt should transition to HALF_OPEN and then try the operation
    await expect(cb.execute(succeedingOperation))
      .resolves
      .toEqual('success');
    
    // Should now be in HALF_OPEN state
    expect(cb.getState()).toBe(CircuitState.HALF_OPEN);
  });

  it('should transition from HALF_OPEN to CLOSED after success threshold', async () => {
    const failingOperation = () => Promise.reject(new Error('Failed'));
    const succeedingOperation = () => Promise.resolve('success');
    
    // Trip the circuit breaker
    for (let i = 0; i < 3; i++) {
      try {
        await cb.execute(failingOperation);
      } catch (e) {
        // Expected to fail
      }
    }
    
    expect(cb.getState()).toBe(CircuitState.OPEN);
    
    // Wait for recovery timeout
    vi.advanceTimersByTime(110);
    
    // First success - transitions to HALF_OPEN
    await cb.execute(succeedingOperation);
    expect(cb.getState()).toBe(CircuitState.HALF_OPEN);
    
    // Second success - should transition to CLOSED
    await cb.execute(succeedingOperation);
    expect(cb.getState()).toBe(CircuitState.CLOSED);
  });

  it('should transition from HALF_OPEN to OPEN on failure', async () => {
    const failingOperation = () => Promise.reject(new Error('Failed'));
    
    // Trip the circuit breaker
    for (let i = 0; i < 3; i++) {
      try {
        await cb.execute(failingOperation);
      } catch (e) {
        // Expected to fail
      }
    }
    
    expect(cb.getState()).toBe(CircuitState.OPEN);
    
    // Wait for recovery timeout
    vi.advanceTimersByTime(110);
    
    await expect(cb.execute(failingOperation)).rejects.toThrow('Failed');
    expect(cb.getState()).toBe(CircuitState.OPEN);

    let executed = false;
    await expect(cb.execute(async () => { executed = true; }))
      .rejects.toThrow(CircuitBreakerOpenError);
    expect(executed).toBe(false);
  });

  it('should reset state manually', async () => {
    const failingOperation = () => Promise.reject(new Error('Failed'));
    
    // Trip the circuit breaker
    for (let i = 0; i < 3; i++) {
      try {
        await cb.execute(failingOperation);
      } catch (e) {
        // Expected to fail
      }
    }
    
    expect(cb.getState()).toBe(CircuitState.OPEN);
    
    // Manual reset
    cb.reset();
    expect(cb.getState()).toBe(CircuitState.CLOSED);
    expect(cb.getMetrics().failureCount).toBe(0);
    expect(cb.getMetrics().successCount).toBe(0);
  });

  it('should handle successful operations in CLOSED state', async () => {
    const succeedingOperation = () => Promise.resolve('success');
    
    const result = await cb.execute(succeedingOperation);
    expect(result).toBe('success');
    expect(cb.getState()).toBe(CircuitState.CLOSED);
  });
});

// Example test for fallback mechanism (would require mocking)
// describe('CircuitBreaker with fallback', () => {
//   it('should return fallback value when circuit is OPEN', async () => {
//     const cb = new CircuitBreaker('test-fallback', {
//       failureThreshold: 2,
//       recoveryTimeoutMs: 1000,
//       successThreshold: 1,
//       onOpen: () => Promise.resolve('fallback-value')
//     });
     
//     // Trip the circuit
//     await cb.execute(() => Promise.reject(new Error('Failed')));
//     await cb.execute(() => Promise.reject(new Error('Failed')));
     
//     expect(cb.getState()).toBe(CircuitState.OPEN);
//     
//     // Should return fallback value
//     const result = await cb.execute(() => Promise.reject(new Error('Failed')));
//     expect(result).toBe('fallback-value');
//   });
// });
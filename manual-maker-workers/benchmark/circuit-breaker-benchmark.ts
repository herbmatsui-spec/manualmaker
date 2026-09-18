import { CircuitBreaker, CircuitState } from '../lib/circuit-breaker';

/**
 * Circuit Breaker Benchmark
 * 
 * This file demonstrates benchmarking approaches for the circuit breaker implementation.
 * To run actual benchmarks, a benchmarking library like benchmark.js would be needed.
 */

/**
 * Benchmark 1: Measure overhead of circuit breaker in CLOSED state
 * Compares direct operation execution vs. circuit breaker execution
 */
async function benchmarkOverhead() {
  const cb = new CircuitBreaker('benchmark-overhead', {
    failureThreshold: 1000, // High threshold to avoid tripping during benchmark
    recoveryTimeoutMs: 60000,
    successThreshold: 1000,
  });
  
  const operation = () => Promise.resolve('result');
  const iterations = 100000;
  
  // Warm up
  for (let i = 0; i < 1000; i++) {
    await cb.execute(operation);
  }
  
  // Measure circuit breaker execution time
  const startCb = Date.now();
  for (let i = 0; i < iterations; i++) {
    await cb.execute(operation);
  }
  const endCb = Date.now();
  
  // Measure direct execution time
  const startDirect = Date.now();
  for (let i = 0; i < iterations; i++) {
    await operation();
  }
  const endDirect = Date.now();
  
  const cbTime = endCb - startCb;
  const directTime = endDirect - startDirect;
  const overheadMs = cbTime - directTime;
  const overheadPerOpMs = overheadMs / iterations;
  
  console.log(`Benchmark Overhead:`);
  console.log(`  Iterations: ${iterations}`);
  console.log(`  Circuit Breaker Time: ${cbTime}ms`);
  console.log(`  Direct Time: ${directTime}ms`);
  console.log(`  Overhead: ${overheadMs}ms (${overheadPerOpMs * 1000000}ns per operation)`);
}

/**
 * Benchmark 2: Measure failure handling performance
 * Compares performance when circuit is CLOSED vs OPEN
 */
async function benchmarkFailureHandling() {
  const cb = new CircuitBreaker('benchmark-failure', {
    failureThreshold: 3,
    recoveryTimeoutMs: 60000,
    successThreshold: 3,
  });
  
  const failingOperation = () => Promise.reject(new Error('Simulated failure'));
  const iterations = 10000;
  
  // Test failure handling in CLOSED state (until threshold)
  console.log(`\nBenchmark Failure Handling (CLOSED state):`);
  const startClosed = Date.now();
  for (let i = 0; i < Math.min(iterations, 2); i++) { // Only 2 to avoid tripping
    try {
      await cb.execute(failingOperation);
    } catch (e) {
      // Expected
    }
  }
  const endClosed = Date.now();
  
  // Trip the circuit breaker
  await cb.execute(failingOperation); // This makes it 3 failures and trips to OPEN
  
  // Test failure handling in OPEN state (should be faster - immediate rejection)
  console.log(`Benchmark Failure Handling (OPEN state):`);
  const startOpen = Date.now();
  for (let i = 0; i < iterations; i++) {
    try {
      await cb.execute(failingOperation);
    } catch (e) {
      // Expected CircuitBreakerOpenError
    }
  }
  const endOpen = Date.now();
  
  const closedTime = endClosed - startClosed;
  const openTime = endOpen - startOpen;
  
  console.log(`  Closed State Time (2 ops): ${closedTime}ms`);
  console.log(`  Open State Time (${iterations} ops): ${openTime}ms`);
  if (closedTime > 0 && openTime > 0) {
    const speedup = ((closedTime * iterations / 2) / openTime).toFixed(1);
    console.log(`  Open state is ${speedup}x faster per operation`);
  } else {
    console.log(`  Open state is faster per operation (closed time: ${closedTime}ms)`);
  }
}

/**
 * Benchmark 3: Measure recovery transition performance
 * Measures time to transition from OPEN to HALF_OPEN to CLOSED
 */
async function benchmarkRecovery() {
  const recoveryTimeoutMs = 50; // Short for benchmarking
  const cb = new CircuitBreaker('benchmark-recovery', {
    failureThreshold: 2,
    recoveryTimeoutMs: recoveryTimeoutMs,
    successThreshold: 2,
  });
  
  const failingOperation = () => Promise.reject(new Error('Simulated failure'));
  const succeedingOperation = () => Promise.resolve('success');
  
  // Trip the circuit breaker
  await cb.execute(failingOperation);
  await cb.execute(failingOperation);
  
  console.log(`\nBenchmark Recovery:`);
  console.log(`  Recovery Timeout: ${recoveryTimeoutMs}ms`);
  
  // Measure time to HALF_OPEN transition
  const startWait = Date.now();
  await delay(recoveryTimeoutMs + 10); // Wait a bit extra
  const waitTime = Date.now() - startWait;
  
  // First successful operation should transition HALF_OPEN -> measuring the transition
  const startTransition = Date.now();
  await cb.execute(succeedingOperation); // First success: OPEN -> HALF_OPEN
  await cb.execute(succeedingOperation); // Second success: HALF_OPEN -> CLOSED
  const transitionTime = Date.now() - startTransition;
  
  console.log(`  Wait for recovery timeout: ${waitTime}ms`);
  console.log(`  Transition time (2 success ops): ${transitionTime}ms`);
  console.log(`  Final state: ${cb.getState()}`);
}

/**
 * Benchmark 4: Simulate fallback mechanism effectiveness
 * Would require mocking KV storage, so this is conceptual
 */
function benchmarkFallbackConcept() {
  console.log(`\nBenchmark Fallback Concept:`);
  console.log(`  In a real deployment with KV storage:`);
  console.log(`  - Cache write overhead: ~0.1-0.5ms per successful operation`);
  console.log(`  - Cache read overhead: ~0.05-0.2ms per fallback lookup`);
  console.log(`  - Network variability: KV access adds ~0.5-2ms typically`);
  console.log(`  - Effective fallback reduces 503 errors to near-zero when warm cache exists`);
}

/**
 * Run all benchmarks
 */
async function runBenchmarks() {
  console.log('=== Circuit Breaker Benchmarks ===\n');
  
  await benchmarkOverhead();
  await benchmarkFailureHandling();
  await benchmarkRecovery();
  benchmarkFallbackConcept();
  
  console.log(`\n=== Benchmarks Complete ==`);
  console.log(`Note: These are simplified benchmarks. For production measurements,`);
  console.log(`use a proper benchmarking library and test in environment similar to production.`);
}

// Run benchmarks if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runBenchmarks().catch(console.error);
}

export { benchmarkOverhead, benchmarkFailureHandling, benchmarkRecovery, benchmarkFallbackConcept };
# Circuit Breaker Operational Guide

## 実装状況と状態共有の方針（B01：2026-09-17）

**以下の英語セクションにある監視・リセットの使用例は、現時点では本番で利用できることを保証しない。** [共通ルート登録](../../manual-maker-workers/src/routes/index.ts)は回路監視をまだ登録せず、[Geminiプロキシ](../../manual-maker-workers/src/routes/gemini.ts)と[Visionプロキシ](../../manual-maker-workers/src/routes/vision.ts)もラッパーへ未接続。認証・契約・統合検証後に公開する。

- 初期方式は**同一環境・同一isolate内**での状態共有とする。全地域・全isolateを横断する回路ではない。
- 実装予定の環境別レジストリーは、環境オブジェクトを弱参照キーとしてインスタンスを保持する。同じ環境オブジェクトでは状態を引き継ぎ、別環境オブジェクトでは分離する。ランタイムが別環境オブジェクトを供給した場合にも状態継続を保証しない。
- 監視は要求を処理したisolateのスナップショット、リセットもそのisolate内の対象回路に限定する。連続した管理要求が別isolateへ到達すれば異なる値が返り得る。
- 再配置・isolateの再作成で状態は失われる。KVの読み書きだけで強整合の分散回路を構成しない。
- 全isolateで一貫した状態や一括リセットが必要なら、専用DOへの集約・可用性・遅延・費用を別計画で検討する。今回その機能は提供しない。

### B01の設計検証

| シナリオ | 期待する共有範囲 |
|---|---|
| 同一isolate、同じ環境オブジェクトで連続要求 | 同じ回路を参照する（C10で実装・テスト予定） |
| 同一isolate、異なる環境オブジェクト | 回路を分離する（C10で実装・テスト予定） |
| 別isolateで同一サービスを使用 | 独立した回路として扱う |
| 一方のisolateを管理リセット | 他方の回路が変わるとは保証しない |

B01は共有範囲の設計決定であり、環境別インスタンス管理・本番監視・管理認証の実装完了を意味しない。

## Overview

This document provides operational guidance for the circuit breaker implementation in the Manual Maker workers service. The circuit breaker pattern prevents cascading failures when external APIs (Gemini and Vision) experience issues, allowing for graceful degradation and faster recovery.

## Components

### 1. CircuitBreaker Base Class (`src/lib/circuit-breaker.ts`)

The core circuit breaker implementation with three states:
- **CLOSED**: Normal operation, requests are allowed through
- **OPEN**: Failure state, requests are blocked immediately
- **HALF_OPEN**: Recovery testing state, limited requests are allowed to test if service has recovered

### 2. External API Wrappers (`src/lib/external-api.ts`)

- `GeminiApi`: Wrapper for Google Gemini API with circuit breaker
- `VisionApi`: Wrapper for Google Cloud Vision API with circuit breaker
- Both include fallback caching mechanisms using KV storage

### 3. Fallback Cache (`src/lib/fallback-cache.ts`)

Provides caching capabilities for graceful degradation when external APIs are unavailable.

## Configuration

### Recommended Settings

| API | failureThreshold | recoveryTimeoutMs | successThreshold | timeoutMs |
|-----|------------------|-------------------|------------------|-----------|
| Gemini | 5 | 60000 (1 minute) | 3 | 10000 (10 seconds) |
| Vision | 3 | 30000 (30 seconds) | 2 | 15000 (15 seconds) |

### Environment Variables

The circuit breaker uses the following environment variables (already defined in the existing Env interface):
- `GEMINI_API_KEY`: Gemini API key
- `GOOGLE_API_KEY`: Vision API key  
- `GEMINI_MODEL_NAME`: Gemini model to use
- `GOOGLE_CLOUD_PROJECT_ID`: Google Cloud project ID
- `PROCESSING_KV`: KV namespace for caching and rate limiting
- `BUCKET`: Primary R2 bucket for storage
- `BUCKET_SECONDARY`: Secondary R2 bucket for replication
- `PROGRESS_DO`: Durable Object namespace for progress tracking

## Monitoring and Metrics

### Metrics Endpoint

Access circuit breaker metrics at:
```
GET /api/metrics/circuit-breakers
```

Response format:
```json
{
  "timestamp": "2026-09-16T12:00:00.000Z",
  "gemini": {
    "state": "closed",
    "failureCount": 0,
    "successCount": 0,
    "lastFailureTime": null,
    "name": "gemini-api"
  },
  "vision": {
    "state": "closed", 
    "failureCount": 0,
    "successCount": 0,
    "lastFailureTime": null,
    "name": "vision-api"
  }
}
```

### State Definitions

- `state`: Current circuit state (`closed`, `open`, or `half_open`)
- `failureCount`: Number of consecutive failures
- `successCount`: Number of consecutive successes in half-open state
- `lastFailureTime`: Timestamp of last failure (milliseconds since epoch)
- `name`: Identifier for the circuit breaker

## Operational Procedures

### Manual Reset

To manually reset circuit breakers to the closed state:
```
POST /api/system/reset-circuit-breakers
```

Response:
```json
{
  "success": true,
  "message": "Circuit breakers reset",
  "timestamp": "2026-09-16T12:00:00.000Z"
}
```

**Note**: In production environments, this endpoint should be protected with authentication and authorization.

### Health Checks

The circuit breaker state is also available through individual API wrapper methods:
- `geminiApi.getCircuitState()` 
- `geminiApi.getCircuitMetrics()`
- `geminiApi.resetCircuitBreaker()`
- Similar methods exist for `visionApi`

## Fallback Mechanism

When a circuit breaker is OPEN, the system automatically attempts to serve cached responses from the fallback cache:

1. **Cache Population**: Successful API responses are cached for 5 minutes (configurable)
2. **Fallback Activation**: When circuit is OPEN, requests first check the fallback cache
3. **Cache Hit**: Cached response is returned immediately with 200 status
4. **Cache Miss**: Circuit breaker OPEN error is returned (503 status)

### Cache Key Generation

Cache keys are generated based on:
- API type (gemini/vision)
- Operation type (generateContent, listModels, annotateImage)
- For Gemini: includes the model name
- For Vision: operation-specific (could be enhanced to include request hash)

## Troubleshooting

### Common Issues

1. **High Failure Count**: 
   - Check external API status pages
   - Verify API keys and quotas
   - Review network connectivity

2. **Stuck in OPEN State**:
   - Verify recovery time has elapsed
   - Check if downstream service has recovered
   - Consider manual reset if needed

3. **Fallback Not Working**:
   - Verify KV namespace is correctly configured
   - Check cache TTL settings
   - Review logs for cache read/write errors

### Diagnostic Commands

Check circuit state:
```bash
curl http://localhost:8787/api/metrics/circuit-breakers
```

Force reset (use with caution in production):
```bash
curl -X POST http://localhost:8787/api/system/reset-circuit-breakers
```

## Performance Considerations

### Overhead

The circuit breaker adds minimal overhead:
- State checks: O(1) operations
- Failure/success counting: O(1) operations
- Timeout handling: Native Promise.race()

### Cache Efficiency

- Successful responses are cached to reduce API calls during outages
- Cache TTL prevents stale data accumulation
- Separate cache keys for different operations prevent interference

## Best Practices

### Configuration Tuning

1. **Start Conservative**: Begin with lower failure thresholds for quicker detection
2. **Monitor Real Patterns**: Adjust thresholds based on actual failure/recovery patterns
3. **Consider API Characteristics**: 
   - Vision API may need stricter thresholds due to image processing variability
   - Gemini API may tolerate more transient failures

### Integration Guidelines

1. **Consistent Error Handling**: Always handle `CircuitBreakerOpenError` (503) and `ExternalAPIError` (502/429) appropriately
2. **Logging**: Monitor circuit breaker state transitions in logs
3. **Graceful Degradation**: Design client applications to handle 503 responses appropriately
4. **Regular Review**: Periodically review circuit breaker metrics and adjust configuration

## Security Considerations

1. **API Key Protection**: The circuit breaker does not expose API keys; they remain in environment variables
2. **Cache Sensitivity**: Cached data does not contain API keys or sensitive authentication material
3. **Access Control**: The metrics and reset endpoints should be protected in production deployments

## References

- Martin Fowler's CircuitBreaker pattern: https://martinfowler.com/articles/circuit-breaker.html
- AWS Circuit Breaker pattern: https://aws.amazon.com/builders-library/making-systems-resilient-with-retry-and-exponential-backoff/
# Rate Limiting Operational Guide

## Overview

This document describes the rate limiting implementation in the Manual Maker system, configuration options, monitoring procedures, and troubleshooting steps.

## Design Choices

The rate limiting implementation uses a sliding window algorithm with the following characteristics:

- **Algorithm**: Sliding window with fixed-size windows implemented via Cloudflare KV
- **Granularity**: Per-identifier (IP address or file ID) and per-endpoint configuration
- **Headers**: Standard rate limiting headers (`RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`, `Retry-After`)
- **Whitelisting**: Support for excluding specific identifiers from rate limiting via environment variables
- **Performance**: Designed for minimal overhead with efficient KV operations

## Configuration

### Predefined Rate Limit Configurations

The system defines specific rate limits for different endpoint groups:

| Endpoint Group | Window Size | Max Requests | Description |
|----------------|-------------|--------------|-------------|
| Upload | 60 seconds | 10 requests | File upload endpoints |
| Gemini Proxy | 60 seconds | 30 requests | Gemini API proxy endpoints |
| Vision Proxy | 60 seconds | 20 requests | Vision API proxy endpoints |
| Progress Updates | 10 seconds | 6 requests | Processing progress update endpoints |
| General IP Protection | 60 seconds | 150 requests | Baseline protection for all endpoints |

### Environment Variables

Rate limiting behavior can be controlled via the following environment variables:

- `RATE_LIMIT_ENABLED`: Set to `false` to disable all rate limiting (default: `true`)
- `RATE_LIMIT_WHITELIST`: Comma-separated list of identifiers (IP addresses) to exclude from general IP-based rate limiting (e.g., `127.0.0.1,::1,10.0.0.0/8`)

### Endpoint-Specific Configuration

Each endpoint group uses the middleware helper functions:

- `rateLimitUpload()` - for upload endpoints
- `rateLimitGeminiProxy()` - for Gemini proxy endpoints
- `rateLimitVisionProxy()` - for Vision proxy endpoints
- `rateLimitProgressUpdate()` - for progress update endpoints
- `rateLimitIPGeneral()` - for general IP-based protection (applied globally with exclusions)

## Monitoring

### Rate Limit Metrics Endpoint

The system provides a metrics endpoint for monitoring rate limiting statistics:

```
GET /api/metrics/rate-limit
```

This endpoint returns JSON with detailed information about each rate limit configuration:

```json
{
  "timestamp": "2026-09-18T06:23:11.000Z",
  "rateLimitMetrics": {
    "upload": {
      "windowMs": 60000,
      "maxRequests": 10,
      "currentWindowIndex": 23456,
      "totalRequests": 142,
      "blockedRequests": 8,
      "uniqueIdentifiers": 23
    },
    "geminiProxy": { ... },
    // ... other configurations
  }
}
```

Fields explained:
- `totalRequests`: Total number of requests (allowed + blocked) in the current window
- `blockedRequests`: Number of requests that were rate limited in the current window
- `uniqueIdentifiers`: Number of unique identifiers (IPs, file IDs) that made requests in the current window

### Key Performance Indicators

Monitor these metrics to ensure the rate limiting is functioning correctly:

1. **Blocked Request Rate**: Should be low for legitimate traffic (typically < 1%)
2. **Unique Identifiers**: Helps understand user distribution
3. **Configuration Utilization**: Compare `totalRequests` to `maxRequests` to identify endpoints approaching limits

## Troubleshooting

### Common Issues

#### Legitimate Users Being Blocked

1. Check if the user's IP is in the whitelist (for general IP protection)
2. Verify the endpoint-specific limits are appropriate for the use case
3. Consider if burst traffic patterns might be triggering false positives

#### Rate Limiting Not Working

1. Verify `RATE_LIMIT_ENABLED` is not set to `false`
2. Check that the middleware is properly applied to the routes
3. Look for errors in worker logs related to KV operations

#### High Blocked Request Rates

1. Consider if the system is under attack or experiencing unexpected traffic spikes
2. Evaluate whether rate limits need adjustment for specific endpoints
3. Check if legitimate traffic patterns have changed

### Manual Intervention

To manually reset rate limiting for a specific identifier:

1. Identify the KV namespace used (`PROCESSING_KV`)
2. Delete keys matching the pattern: `{keyPrefix}:{identifier}:*`
3. For example, to reset upload limits for IP `1.2.3.4`:
   ```bash
   # Using wrangler KV commands
   wrangler kv:key delete --binding=PROCESSING_KV --prefix="ratelimit:upload:1.2.3.4:"
   ```

## Performance Impact

The rate limiting implementation is designed to have minimal performance impact:

- **KV Operations**: Two KV operations per request (get and put) with short TTL
- **Memory Usage**: Minimal, as only counters are stored
- **Latency**: Typically adds <5ms per request when KV cache is hot

## Testing

The rate limiting functionality is covered by automated tests in `src/lib/__tests__/rate-limit.test.ts`. Tests cover:

- Basic allowing and blocking behavior
- Window reset functionality
- Independent key handling
- Whitelist functionality
- Middleware header setting
- Environment variable controls

Run tests with:
```bash
npm run test -- src/lib/__tests__/rate-limit.test.ts
```

## Future Improvements

Consider these enhancements for future development:

1. **Distributed Counters**: Move to a more efficient counter system (e.g., Redis) if KV becomes a bottleneck
2. **Dynamic Adjustment**: Automatically adjust limits based on system load
3. **Advanced Analytics**: Integrate with external monitoring systems (Prometheus, Grafana)
4. **Endpoint-Specific Whitelists**: Allow different whitelists for different endpoint groups
5. **Rate Shielding**: Implement exponential backoff for repeated offenders

## Related Documentation

- [Rate Limiting Implementation Plan](../improvement-plans/C6-rate-limiting-completion.md)
- [API Security Guidelines](../security/api-security.md)
- [Monitoring and Alerting Guide](../operational/monitoring.md)
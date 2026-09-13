# Cloudflare Workers Deployment Guide for SecurityManager

## Overview
This guide explains how to deploy the SecurityManager module to Cloudflare Workers as a standalone backend-independent service.

## Prerequisites
- [Wrangler](https://developers.cloudflare.com/workers/cli-wrangler/install-update/) installed
- A Cloudflare Workers site configured

## Step 1: Configure KV Namespaces
In your `wrangler.toml`, add two KV namespaces:

```toml
[[kv_namespaces]]
binding = "PII_PATTERNS"
id = "your-pii-patterns-kv-id"

[[kv_namespaces]]
binding = "API_KEYS"
id = "your-api-keys-kv-id"
```

## Step 2: Set Encryption Key Secret
Generate a 32-byte encryption key (base64 encoded):

```bash
# Generate a random key
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```

Then set it as a secret:

```bash
wrangler secret put ENCRYPTION_KEY
# Paste the generated key when prompted
```

## Step 3: Use the SecurityManager in Your Worker
In your Worker entry point (e.g., `src/index.js` or `src/index.ts`), import and use the SecurityManager with the Workers-optimized configuration:

### Example (JavaScript)
```javascript
import { SecurityManager } from './manual_processor/src/security_manager.js';
import { create_workers_config } from './manual_processor/src/security/strategies_workers.js';

// Initialize with Workers-optimized config
const config = create_workers_config();

export default {
  async fetch(request) {
    const { searchParams } = new URL(request.url);
    const text = searchParams.get('text') || '';
    
    const [masked, info] = SecurityManager.mask_sensitive_data(text, config);
    
    return new Response(JSON.stringify({
      original: text,
      masked: masked,
      info: info
    }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
```

### Example (TypeScript)
```typescript
import { SecurityManager } from './manual_processor/src/security_manager';
import { create_workers_config } from './manual_processor/src/security/strategies_workers';

const config = create_workers_config();

export default {
  async fetch(request): Promise<Response> {
    const { searchParams } = new URL(request.url);
    const text = searchParams.get('text') || '';
    
    const [masked, info] = SecurityManager.mask_sensitive_data(text, config);
    
    return new Response(JSON.stringify({
      original: text,
      masked: masked,
      info: info
    }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
```

## Step 4: Deploy
```bash
wrangler publish
```

## Verification
After deployment, you can test the endpoint:

```bash
curl "https://your-worker.your-subdomain.workers.dev/?text=Email%3A%20test%40example.com"
```

Expected response:
```json
{
  "original": "Email: test@example.com",
  "masked": "Email: [REDACTED_EMAIL]",
  "info": {
    "counts": { "EMAIL": 1 }
  }
}
```

## Notes
- The SecurityManager uses Cloudflare Workers KV for PII patterns and API key storage.
- Encryption uses the Web Crypto API available in Workers runtime.
- If KV namespaces are not available (e.g., during local development without wrangler dev), the system falls back to in-memory patterns and environment variables for API keys.
- Encryption requires the `ENCRYPTION_KEY` secret to be set; otherwise, operations are performed without encryption (data remains plaintext).

## Troubleshooting
- **"KV namespace not found"**: Ensure the KV namespace IDs in wrangler.toml match those created in your Cloudflare account.
- **Encryption not working**: Verify that `ENCRYPTION_KEY` is set as a secret (not just an environment variable) and is a valid base64-encoded 32-byte key.
- **Missing patterns**: Make sure to populate the PII_PATTERNS KV namespace with a JSON object containing a "patterns" array. Example:
  ```json
  {
    "patterns": [
      {
        "name": "EMAIL",
        "regex": "\\S+@\\S+\\.\\S+",
        "mask": "[REDACTED]",
        "enabled": true
      }
    ]
  }
  ```

## Security Considerations
- Never hard-code encryption keys in your source code.
- Use separate KV namespaces for different environments (preview/production).
- Regularly rotate encryption keys by updating the secret and re-encrypting existing data.
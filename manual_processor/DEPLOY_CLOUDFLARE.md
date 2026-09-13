# Manual Processor - Cloudflare Deployment Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Cloudflare Edge                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Workers (Edge Layer)                                    │    │
│  │  - Authentication / Authorization                         │    │
│  │  - CORS Handling                                          │    │
│  │  - Rate Limiting (KV)                                     │    │
│  │  - Request Routing → Pages Functions                      │    │
│  │  - WebSocket Proxy                                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                    │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Pages Functions (Python 3.11)                          │    │
│  │  - API Handlers (/api/*)                                │    │
│  │  - File Upload → R2                                     │    │
│  │  - Queue Producer (PDF Processing)                      │    │
│  │  - Progress Tracking (Durable Objects)                  │    │
│  │  - Mermaid Diagram Operations                           │    │
│  │  - Google Drive Integration                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                    │
│              ┌───────────────┼───────────────┐                   │
│              ▼               ▼               ▼                   │
│        ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│        │   R2     │    │  Queue   │    │   DO     │             │
│        │ (Files)  │    │ (Async)  │    │ (WS)     │             │
│        └──────────┘    └──────────┘    └──────────┘             │
│              │               │                                    │
│              ▼               ▼                                    │
│        ┌──────────────────────────────┐                          │
│        │  Python Queue Consumer       │                          │
│        │  - PDF Processing            │                          │
│        │  - OCR (Gemini/Vision API)   │                          │
│        │  - Document Generation       │                          │
│        └──────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Cloudflare Account** with Workers Paid Plan (for Python Workers)
2. **Node.js 20+** and **pnpm** (or npm)
3. **Python 3.11+** (for local testing)
4. **Wrangler CLI**: `npm install -g wrangler`
5. **Google Cloud Account** (for Vision API / Gemini API)

## Setup Steps

### 1. Create Cloudflare Resources

```bash
# Login to Cloudflare
wrangler login

# Create R2 bucket
wrangler r2 bucket create manual-processor-files
wrangler r2 bucket create manual-processor-files-preview

# Create Queue
wrangler queues create pdf-processing
wrangler queues create pdf-processing-dlq

# Create KV namespace for rate limiting
wrangler kv namespace create RATE_LIMIT_KV
wrangler kv namespace create RATE_LIMIT_KV --preview

# Note the KV namespace IDs and update wrangler.toml
```

### 2. Configure Secrets

```bash
# Set secrets for Pages Functions
wrangler pages secret put GOOGLE_API_KEY --project-name=manual-processor
wrangler pages secret put GEMINI_API_KEY --project-name=manual-processor
wrangler pages secret put ENCRYPTION_KEY --project-name=manual-processor
wrangler pages secret put JWT_SECRET --project-name=manual-processor

# Set secrets for Queue Consumer (Python Worker)
wrangler secret put GOOGLE_API_KEY --config wrangler.queue.toml
wrangler secret put GEMINI_API_KEY --config wrangler.queue.toml
wrangler secret put ENCRYPTION_KEY --config wrangler.queue.toml
```

### 3. Update wrangler.toml

Edit `manual_processor/wrangler.toml` and update:
- KV namespace IDs (from step 1)
- R2 bucket names (if different)
- Service binding name

### 4. Local Development

```bash
# Install dependencies
cd manual_processor
pip install -r requirements-pages.txt --target .python_packages

# Start local development (requires MinIO for R2, local queue)
# Option 1: Use wrangler dev (limited Python support)
wrangler pages dev manual_processor/functions --binding FILES=manual-processor-files-local

# Option 2: Run FastAPI locally for full testing
cd manual_processor
python -m src.web.app
```

### 5. Deploy

```bash
# Deploy Pages Functions (main API)
cd manual_processor
wrangler pages deploy . --project-name=manual-processor

# Deploy Queue Consumer (Python Worker)
wrangler deploy --config wrangler.queue.toml

# Deploy Edge Worker
cd workers
npm install
npm run build:worker
wrangler deploy
```

### 6. Configure Custom Domain (Optional)

```bash
# Add custom domain to Pages project
wrangler pages project create manual-processor --production-branch main
# Then add custom domain in Cloudflare Dashboard > Pages > manual-processor > Custom domains
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Google Cloud Vision API key |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `ENCRYPTION_KEY` | No | 32-byte base64 key for encryption |
| `JWT_SECRET` | No | JWT signing secret |
| `GOOGLE_CLOUD_PROJECT_ID` | No | GCP project for Vision API |
| `R2_BUCKET_NAME` | No | R2 bucket name (default: manual-processor-files) |
| `ENVIRONMENT` | No | production/preview/development |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins |

## Project Structure

```
manual_processor/
├── functions/                    # Pages Functions (Python)
│   ├── __init__.py              # Main router
│   ├── api/                     # API handlers
│   │   ├── config.py            # Health, config, i18n
│   │   ├── upload.py            # File upload to R2
│   │   ├── process.py           # Queue-based processing
│   │   ├── download.py          # File download from R2
│   │   ├── security.py          # PII masking, audit logs
│   │   ├── ws_progress.py       # WebSocket progress
│   │   ├── mermaid.py           # Diagram operations
│   │   ├── drive.py             # Google Drive integration
│   │   └── observability.py     # Prometheus metrics
│   ├── queue/                   # Queue consumer
│   │   ├── __init__.py
│   │   └── pdf_processor.py     # PDF processing worker
│   └── _middleware/             # Shared middleware
│       ├── __init__.py          # CORS, rate limit, auth
│       └── progress_do.py       # Durable Object (Python stub)
├── workers/                     # Edge Worker (TypeScript)
│   ├── index.ts                 # Main edge worker
│   ├── progress_do.js           # Durable Object implementation
│   ├── package.json
│   └── tsconfig.json
├── src/                         # Shared Python modules
│   ├── r2_storage.py            # R2 storage abstraction
│   ├── processor/               # Document processing
│   └── ...                      # Other modules
├── config/                      # Configuration
│   ├── cloudflare_config.py     # Cloudflare-aware config
│   ├── settings.py              # Pydantic settings
│   └── config.py                # Legacy compatibility
├── requirements-pages.txt       # Python deps for Pages
├── wrangler.toml               # Pages + Workers config
├── wrangler.queue.toml         # Queue consumer config
└── .dev.vars.example           # Local dev variables template
```

## Key Differences from FastAPI Version

| Feature | FastAPI | Pages Functions |
|---------|---------|-----------------|
| **File Storage** | Local filesystem | R2 (S3-compatible) |
| **Async Processing** | In-memory thread pool | Cloudflare Queues |
| **WebSocket** | Native FastAPI WS | Durable Objects |
| **Rate Limiting** | Middleware | KV-based (Edge) |
| **Deployment** | Docker/VM | Serverless (edge) |
| **Scaling** | Manual | Automatic |
| **Cost** | Fixed | Pay-per-request |

## Testing Deployment

```bash
# Test health endpoint
curl https://manual-processor.pages.dev/api/health

# Test file upload
curl -X POST -F "file=@test.pdf" https://manual-processor.pages.dev/api/upload

# Test processing
curl -X POST https://manual-processor.pages.dev/api/process/{file_id} \
  -H "Content-Type: application/json" \
  -d '{"compact_layout": false, "use_emojis": false}'

# Check result
curl https://manual-processor.pages.dev/api/results/{file_id}

# Download result
curl https://manual-processor.pages.dev/api/download/{file_id}/pdf
```

## Monitoring

- **Logs**: Cloudflare Dashboard > Workers/Pages > Logs
- **Metrics**: `/metrics` endpoint (Prometheus format)
- **Queue**: Cloudflare Dashboard > Queues > pdf-processing
- **R2**: Cloudflare Dashboard > R2 > manual-processor-files

## Troubleshooting

### Python Worker Not Starting
- Check `wrangler deploy --config wrangler.queue.toml` output
- Verify Python version compatibility (3.11)
- Check dependencies in `requirements-pages.txt`

### Queue Messages Not Processing
- Check Queue consumer logs
- Verify `PDF_QUEUE` binding in `wrangler.queue.toml`
- Check dead letter queue for failed messages

### R2 Access Denied
- Verify R2 bucket permissions
- Check `FILES` binding in `wrangler.toml`
- Ensure API token has R2 permissions

### WebSocket Not Connecting
- Verify Durable Object migration applied
- Check `PROGRESS_DO` binding
- Check Edge Worker WebSocket proxy

## Cost Optimization

- **Pages Functions**: Free tier includes 100,000 requests/day
- **Workers**: Free tier includes 100,000 requests/day
- **R2**: 10 GB free storage, Class A/B operations free
- **Queues**: 1 million messages/month free
- **Durable Objects**: 1 million requests/month free

For production workloads, expect ~$5-20/month depending on usage.
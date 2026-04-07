# IQinsyt Backend

FastAPI-based async research API that powers the IQinsyt Chrome extension. It accepts event/topic titles, performs real-time web searches, generates neutral structured analysis via GPT-4o-mini, and enforces a strict compliance layer to prevent predictive or biased language.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Research Pipeline](#research-pipeline)
- [Compliance & Neutrality](#compliance--neutrality)
- [Authentication](#authentication)
- [Caching Strategy](#caching-strategy)
- [Database Schema](#database-schema)
- [Logging](#logging)
- [Development](#development)
- [Deployment](#deployment)
- [Future Roadmap](#future-roadmap)

---

## Architecture Overview

```
Chrome Extension ──HTTP──► FastAPI Backend ──► Brave Search API (web context)
                              │
                              ├──► OpenAI GPT-4o-mini (structured analysis)
                              │
                              ├──► Compliance Engine (36 regex patterns, 3-attempt loop)
                              │
                              └──► MongoDB (cache + history)
```

The backend is the **AI research engine** of the IQinsyt platform. Its sole responsibility is:

1. Receive an event/topic from the Chrome extension
2. Gather real-time web context via Brave Search
3. Generate neutral, factual analysis via GPT-4o-mini
4. Enforce strict compliance rules to block predictive/biased language
5. Return structured research with 7 defined sections
6. Cache results for 4 hours to avoid redundant work

---

## Project Structure

```
iqinsyt_backend/
├── src/
│   ├── __init__.py
│   │
│   ├── api/                          # HTTP layer (FastAPI routes)
│   │   ├── __init__.py
│   │   ├── server.py                 # App factory, middleware, lifespan, health
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── research.py           # POST /v1/research endpoint
│   │       └── schemas.py           # Pydantic schemas: ResearchRequest, ResearchSections, ResearchResponse, APIResponse
│   │
│   ├── core/                         # Shared infrastructure
│   │   ├── __init__.py
│   │   ├── config.py                 # Pydantic Settings (reads .env)
│   │   ├── dependencies.py           # FastAPI Depends() — API key auth
│   │   ├── exceptions.py             # Custom exception + error handlers
│   │   └── logging_config.py         # ColoredFormatter, JsonFormatter, setup
│   │
│   ├── db/                           # Database lifecycle, models, hash helpers
│   │   ├── __init__.py               # init/close MongoDB + cache/fingerprint helpers
│   │   └── models.py                 # Beanie documents: research_cache/history
│   │
│   └── services/                     # Business logic
│       ├── __init__.py
│       ├── cache_service.py          # MongoDB 4-hour TTL cache
│       ├── compliance_service.py     # Neutrality enforcement (36 regex patterns)
│       ├── llm_service.py            # OpenAI GPT-4o-mini integration
│       ├── research_service.py       # Pipeline orchestrator
│       └── search_service.py         # Brave Search API integration
│
├── .env                              # Local secrets (gitignored)
├── .env.example                      # Environment variable template
├── .gitignore
├── pyproject.toml                    # Dependencies, project metadata
├── server_run.py                     # Production entry point (Gunicorn)
├── README.md                         # This file
├── architecture.md                   # Chrome extension architecture spec
├── architecture_backend.md           # Full backend architecture spec
└── architecture_webapp.md            # Web app architecture spec
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Framework** | FastAPI (Python 3.12, async) |
| **Server** | Gunicorn + Uvicorn workers (production) |
| **Database** | MongoDB via Beanie ODM + Motor async driver |
| **LLM** | OpenAI GPT-4o-mini (async SDK) |
| **Web Search** | Brave Search API |
| **HTTP Client** | httpx (async) |
| **Settings** | pydantic-settings + python-dotenv |
| **Package Manager** | uv |

---

## Prerequisites

- **Python 3.12+**
- **MongoDB** — local or Atlas connection string
- **API Keys**:
  - `OPENAI_API_KEY` — OpenAI account
  - `BRAVE_API_KEY` — Brave Search account (free tier available)

---

## Quick Start

### 1. Install dependencies

```bash
# Using uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### 2. Set up environment

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=iqinsyt
API_KEY=your-secret-key-here
OPENAI_API_KEY=sk-proj-...
BRAVE_API_KEY=BSA...
```

### 3. Run the server

**Development** (auto-reload, single worker):

```bash
uv run fastapi dev src.api.server:app
# or
uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000
```

**Production** (Gunicorn + Uvicorn workers):

```bash
uv run python server_run.py
```

### 4. Verify

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"ok","version":"0.1.0"}
```

### 5. Test the research endpoint

```bash
curl -X POST http://localhost:8000/v1/research \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key-here" \
  -d '{
    "eventTitle": "Champions League Final 2025",
    "eventSource": "kalshi.com",
    "timestamp": 1743638400000
  }'
```

---

## Configuration

All configuration is managed through environment variables or a `.env` file. The settings are defined in `src/core/config.py` using pydantic-settings.

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB_NAME` | `iqinsyt` | Database name |
| `API_KEY` | `dev-key-change-me` | Shared secret for API auth (sent via `X-API-Key` header) |
| `OPENAI_API_KEY` | `""` | OpenAI API key for GPT-4o-mini |
| `BRAVE_API_KEY` | `""` | Brave Search API key |
| `APP_VERSION` | `0.1.0` | App version string |
| `CORS_ORIGINS` | `chrome-extension://*,http://localhost:*` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_JSON_FORMAT` | `false` | Use JSON log format (set `true` for production) |
| `LOG_FILE` | `logs/app.log` | Log file path (empty string disables file logging) |
| `LOG_MAX_BYTES` | `10485760` | Max log file size before rotation (10 MB) |
| `LOG_BACKUP_COUNT` | `5` | Number of rotated log files to keep |

---

## API Endpoints

All responses use a unified envelope:

```python
# src/api/v1/schemas.py
class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    request_id: str
    timestamp: str  # ISO 8601
```

### `GET /health`

Health check — no authentication required.

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "db": "ok",
    "version": "0.1.0"
  },
  "request_id": "uuid-string",
  "timestamp": "2025-04-01T12:00:00Z"
}
```

### `POST /v1/research`

Main research endpoint. Requires `X-API-Key` header.

**Headers:**
```
Content-Type: application/json
X-API-Key: <your-api-key>
```

**Request Body:**
```json
{
  "eventTitle": "string (1-500 chars)",
  "eventSource": "string (1-253 chars)",
  "timestamp": 0          // Unix milliseconds from the extension
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "cached": false,
    "cachedAt": null,
    "sections": {
      "eventSummary": "...",
      "keyVariables": "...",
      "historicalContext": "...",
      "currentDrivers": "...",
      "riskFactors": "...",
      "dataConfidence": "...",
      "dataGaps": "..."
    },
    "dataRetrievalAvailable": true,
    "generatedAt": "2025-04-01T12:00:00Z"
  },
  "request_id": "uuid-string",
  "timestamp": "2025-04-01T12:00:00Z"
}
```

**Error Responses:**

All errors include `success: false`, `error`, `message`, `request_id`, and `timestamp`:

```json
{
  "success": false,
  "error": "INVALID_API_KEY",
  "message": "Invalid or missing API key.",
  "request_id": "uuid-string",
  "timestamp": "2025-04-01T12:00:00Z"
}
```

| Status | Error Code | Cause |
|--------|-----------|-------|
| 401 | `INVALID_API_KEY` | Missing or wrong `X-API-Key` header |
| 422 | — | Invalid request body (Pydantic validation) |
| 503 | `LLM_UNAVAILABLE` | All LLM attempts returned compliance-blocked sections |
| 500 | `INTERNAL_ERROR` | Unexpected server error |

---

## Research Pipeline

The full pipeline is orchestrated in `src/services/research_service.py`:

```
POST /v1/research
    │
    ▼
Step 1: Cache Lookup
    Check MongoDB for a cached result (4-hour TTL, keyed by hashed title + date)
    │
    ├── HIT → Return cached result (fire-and-forget history write)
    │
    └── MISS → Continue
            │
            ▼
Step 2: Web Search
    Run 3 parallel Brave Search queries: "{title} news", "{title} analysis", "{title} preview"
    Deduplicate by URL, cap at 6 results, cap text at 9,000 chars
    │
    ▼
Step 3+4: Compliant LLM Pipeline
    Assemble prompt with system prompt + section instructions + negative constraints
    Call GPT-4o-mini (8s timeout, temperature 0.2, JSON output)
    Scan output against 36 compliance regex patterns
    │
    ├── PASS → Return sections
    │
    ├── FAIL (attempt < 3) → Retry with violated phrases added as "avoid these" constraints
    │
    └── FAIL (attempt 3) → Per-section quarantine (keep compliant sections, placeholder the rest)
            │
            ▼
Step 5: Total Failure Check
    If ALL sections are placeholders → raise 503 IQinsytException
    │
    ▼
Step 6: Persist
    Parallel write: cache update + history record
    │
    ▼
Step 7: Return ResearchResponse
```

---

## Compliance & Neutrality

The compliance engine (`src/services/compliance_service.py`) ensures all research output is neutral, factual, and free of predictive or biased language.

### How It Works

1. LLM generates 7 research sections as JSON
2. Each section is scanned against **36 regex patterns** across 4 categories:
   - **Predictive language**: "likely to", "expected to", "odds favour", "probability of", "forecast", etc.
   - **Recommendation language**: "consider backing", "worth backing", "good pick", "strong case for", etc.
   - **Emotionally charged language**: "dominant", "unstoppable", "inevitably", "sure to", "guaranteed", etc.
   - **Outcome ranking**: "favourite", "underdog", "has the edge", "stronger team", etc.
3. If violations found, the LLM retries (up to 3 attempts) with violated phrases fed back as "avoid these" constraints
4. After 3 failed attempts, **per-section quarantine** is applied — compliant sections are kept, violating sections are replaced with `"[Section unavailable — compliance filter applied]"`

### Why This Matters

The Chrome extension is used for prediction market research. The output must be purely informational — never suggesting which outcome to bet on, never predicting winners, never using emotionally charged language.

---

## Authentication

### Current: API Key (Shared Secret)

All endpoints except `/health` require an `X-API-Key` header matching the `API_KEY` environment variable.

```bash
curl -H "X-API-Key: your-secret-key" http://localhost:8000/v1/research
```

The API key is hashed (SHA-256) and stored as `user_fingerprint` in the research history collection, enabling per-user tracking without storing the raw key.

**Generate a strong key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Planned: JWT Authentication (RS256)

The architecture spec (`architecture_backend.md`) describes a full JWT-based auth system with:
- RS256 asymmetric signing (RSA 2048-bit key pair)
- 15-minute access tokens + 30-day refresh tokens
- Refresh token rotation with replay attack detection
- One-time 8-character auth codes for Chrome extension pairing
- User registration, login, subscription management

**This is not yet implemented.** The current codebase uses API key auth only.

---

## Caching Strategy

### Current: MongoDB TTL Cache

- **TTL**: 4 hours
- **Key**: `sha256(title)[:16]:YYYY-MM-DD`
- **Mechanism**: MongoDB TTL index on `expires_at` field auto-deletes expired documents
- **Behavior**: On cache hit, returns immediately without calling Brave Search or LLM

```python
# Cache key example
# Title: "Champions League Final 2025"
# Key:   "a3f8c2d1e9b7f4a6:2025-04-01"
```

### Planned: 3-Tier Cache

The architecture spec describes a more sophisticated caching strategy:
1. **Redis** — exact-match cache (fast, sub-millisecond)
2. **Pinecone** — semantic similarity cache (fuzzy match for similar topics)
3. **Full pipeline** — Brave Search + LLM (fallback)

---

## Database Schema

Beanie document models are defined in `src/db/models.py`. Connection lifecycle (`init_db`, `close_db`) and hashing helpers (`make_cache_key`, `user_fingerprint`) are defined in `src/db/__init__.py`.

### `research_cache`

Temporary cache entries, auto-deleted by MongoDB TTL index.

| Field | Type | Notes |
|-------|------|-------|
| `cache_key` | string | Unique, `sha256(title)[:16]:YYYY-MM-DD` |
| `event_title` | string | Original event title |
| `request_id` | string | UUID for tracing |
| `sections` | object | 7 research sections |
| `data_retrieval_available` | boolean | Whether web search returned results |
| `generated_at` | datetime | UTC timestamp |
| `expires_at` | datetime | TTL expiry (generated_at + 4 hours) |

### `research_history`

Permanent record of all research requests.

| Field | Type | Notes |
|-------|------|-------|
| `user_fingerprint` | string | SHA-256 hash of API key |
| `event_title` | string | Original event title |
| `event_source` | string | Source domain (e.g., `kalshi.com`) |
| `request_id` | string | Unique UUID |
| `cached` | boolean | Whether result was from cache |
| `data_retrieval_available` | boolean | Web search success |
| `sections` | object | 7 research sections |
| `generated_at` | datetime | UTC timestamp |
| `created_at` | datetime | UTC timestamp |

**Indexes:**
- Compound: `(user_fingerprint ASC, created_at DESC)` — per-user history queries
- Unique: `(request_id ASC)` — deduplication

---

## Logging

### Setup

Logging is configured in `src/core/logging_config.py` and initialized on server startup in the lifespan handler.

### Formats

**Development** (default): Colored console output
```
2025-04-01 12:00:00 - app - INFO - Starting IQinsyt Backend v0.1.0 (server.py:16)
2025-04-01 12:00:01 - api.research - INFO - Research request received: title='Champions League Final', source=kalshi.com, request_id=abc-123 (research.py:48)
2025-04-01 12:00:03 - services.research_service - INFO - Cache MISS for 'Champions League Final' — running pipeline (request_id=abc-123) (research_service.py:51)
```

**Production** (`LOG_JSON_FORMAT=true`): Structured JSON
```json
{"timestamp": "2025-04-01 12:00:00", "level": "INFO", "logger": "app", "message": "Starting IQinsyt Backend v0.1.0", "module": "server", "file": "server.py", "line": 16}
```

### Log Levels

| Level | When Used |
|-------|-----------|
| `INFO` | Startup/shutdown, cache hits/misses, request received, response sent, health checks |
| `WARNING` | API key missing, search failures, LLM retries, compliance violations, degraded health |
| `ERROR` | Unhandled exceptions with full traceback, pipeline failures |

### File Logging

Logs are written to `logs/app.log` with rotation (10 MB max, 5 backups). The `logs/` directory is gitignored.

### Request Tracing

Every request gets a UUID (`request_id`) injected by middleware. This ID flows through:
- All log messages across all services
- Error responses (returned to client)
- Database records (cache + history)

This enables end-to-end tracing of a single request across the entire pipeline.

---

## Development

### Running Tests

No test suite exists yet. The architecture spec (`architecture_backend.md`) contains proposed test code for:
- Auth module (JWT, refresh tokens, replay detection)
- Compliance service (pattern matching, quarantine logic)
- Research pipeline (cache hits, LLM failures)
- Rate limiting
- Load testing (k6)

### Linting & Formatting

The project uses **Ruff** for linting and formatting:

```bash
ruff check src/
ruff format src/
```

### Code Conventions

- **Async-first**: All I/O operations use async/await
- **No blocking calls**: Use `asyncio.wait_for()` for timeouts
- **Fire-and-forget**: Non-critical writes (history) use `asyncio.create_task()` without await
- **Graceful degradation**: Missing API keys skip features rather than crash (e.g., no Brave key → skip web search, LLM still works with general knowledge)
- **Concise logging**: Log metadata only (titles, IDs, error types) — never dump full payloads, context text, or LLM responses

---

## Deployment

### Production Server

```bash
uv run python server_run.py
```

This runs Gunicorn with:
- 2 UvicornWorker processes
- Bind to `0.0.0.0:$PORT` (default 8000)
- 60s timeout (LLM calls can be slow)
- Worker restart every 1000 requests (prevent memory leaks)
- 100-request jitter (stagger restarts)

### Environment Variables for Production

```env
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/
API_KEY=<strong-random-key>
OPENAI_API_KEY=sk-proj-...
BRAVE_API_KEY=BSA...
LOG_LEVEL=INFO
LOG_JSON_FORMAT=true
CORS_ORIGINS=https://yourdomain.com,chrome-extension://your-extension-id
```

### Docker (Proposed)

No Dockerfile exists yet. The architecture spec proposes:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
EXPOSE 8000
CMD ["python", "server_run.py"]
```

---

## Future Roadmap

These features are documented in the architecture specs but **not yet implemented**:

| Feature | Status | Spec |
|---------|--------|------|
| JWT auth (RS256) | Planned | `architecture_backend.md` |
| User registration/login | Planned | `architecture_backend.md` |
| Refresh token rotation + replay detection | Planned | `architecture_backend.md` |
| One-time auth codes for extension pairing | Planned | `architecture_backend.md` |
| Stripe billing (Free/Starter/Pro plans) | Planned | `architecture_backend.md`, `architecture_webapp.md` |
| Redis caching layer | Planned | `architecture_backend.md` |
| Pinecone semantic cache | Planned | `architecture_backend.md` |
| Firecrawl web scraping | Planned | `architecture_backend.md` |
| Rate limiting per plan tier | Planned | `architecture_backend.md` |
| User profile & usage endpoints | Planned | `architecture_backend.md` |
| Compliance audit log | Planned | `architecture_backend.md` |
| Web app (React SPA) | Planned | `architecture_webapp.md` |
| Test suite | Planned | `architecture_backend.md` |
| CI/CD pipeline | Not started | — |
| Docker deployment | Not started | — |

---

## Related Repositories

- **Chrome Extension**: See `architecture.md` for the extension architecture
- **Web App**: See `architecture_webapp.md` for the React SPA architecture

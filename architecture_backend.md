# IQinsyt Backend API — Full Architecture & Developer Guide

> **Scope:** This document covers the Python/FastAPI backend server only — its structure, database schema, AI pipeline, auth system, compliance layer, caching strategy, and everything a developer needs to build it from scratch. The Chrome extension is documented separately in `architecture.md`. The web app frontend is a separate deliverable.

---

## Table of Contents

1. [What Is This Backend?](#1-what-is-this-backend)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Project Structure](#3-project-structure)
4. [API Endpoints — Full Specification](#4-api-endpoints--full-specification)
5. [Auth Module](#5-auth-module)
6. [Insight Module — The AI Pipeline](#6-insight-module--the-ai-pipeline)
7. [Neutrality & Compliance Module](#7-neutrality--compliance-module)
8. [Database Schema](#8-database-schema)
9. [Redis Schema](#9-redis-schema)
10. [Pinecone Schema](#10-pinecone-schema)
11. [Rate Limiting](#11-rate-limiting)
12. [Caching Strategy](#12-caching-strategy)
13. [Error Handling](#13-error-handling)
14. [Environment Variables](#14-environment-variables)
15. [Build & Development Setup](#15-build--development-setup)
16. [Deployment](#16-deployment)
17. [Testing Strategy](#17-testing-strategy)

---

## 1. What Is This Backend?

The IQinsyt backend is a **Python 3.12 / FastAPI async REST API** that powers both the IQinsyt Chrome extension and the IQinsyt web app. It receives event queries, orchestrates a multi-step AI research pipeline, enforces a mandatory neutrality compliance layer, and returns structured 7-section research output.

**What it IS:**
- An async API server built for sub-5-second end-to-end latency on uncached requests
- An orchestration layer across Redis, Pinecone, Brave Search, Firecrawl, and OpenAI
- A compliance enforcement system that guarantees neutral, non-predictive output
- A subscription and billing management layer via Stripe

**What it is NOT:**
- Not a prediction engine — it never returns odds, probabilities, or outcome rankings
- Not a web scraper (it delegates scraping to Firecrawl)
- Not a search engine (it delegates search to Brave)
- Not responsible for rendering UI — it returns JSON only
- Not a real-time streaming service — all responses are synchronous JSON payloads
- Not a stateful session server — all state lives in PostgreSQL, Redis, or Pinecone

---

## 2. High-Level Architecture

```
                    CLIENTS
        ┌────────────────────────────┐
        │  Chrome Extension          │  Chrome extension (Manifest V3)
        │  Web App (React)           │  Browser SPA
        └───────────┬────────────────┘
                    │ HTTPS + JWT (Bearer token)
                    ▼
        ┌───────────────────────────────┐
        │         FastAPI App           │
        │  (Python 3.12, uvicorn/       │
        │   gunicorn, async)            │
        │                               │
        │  ┌─────────────────────────┐  │
        │  │   Middleware Stack       │  │
        │  │   - CORS                 │  │
        │  │   - Request ID inject    │  │
        │  │   - Rate limit (Redis)   │  │
        │  │   - JWT validation       │  │
        │  └────────────┬────────────┘  │
        │               │               │
        │  ┌────────────▼────────────┐  │
        │  │       Routers           │  │
        │  │  /v1/auth    /v1/user   │  │
        │  │  /v1/insight /v1/billing│  │
        │  └────────────┬────────────┘  │
        │               │               │
        │  ┌────────────▼────────────┐  │
        │  │       Services          │  │
        │  │  InsightService         │  │
        │  │  AuthService            │  │
        │  │  BillingService         │  │
        │  │  ComplianceService      │  │
        │  └────────────┬────────────┘  │
        └───────────────┼───────────────┘
                        │
        ┌───────────────┼──────────────────────────────────┐
        │               │  EXTERNAL SERVICES               │
        │               │                                  │
        │    ┌──────────▼──────────┐                       │
        │    │    PostgreSQL        │  Users, tokens,       │
        │    │    (primary DB)      │  history, audit log   │
        │    └─────────────────────┘                       │
        │                                                  │
        │    ┌─────────────────────┐                       │
        │    │    Redis             │  Cache, rate limits,  │
        │    │    (cache/counters)  │  auth codes           │
        │    └─────────────────────┘                       │
        │                                                  │
        │    ┌─────────────────────┐                       │
        │    │    Pinecone          │  Semantic vector      │
        │    │    (vector DB)       │  similarity search    │
        │    └─────────────────────┘                       │
        │                                                  │
        │    ┌─────────────────────┐                       │
        │    │  Brave Search API   │  Public web search    │
        │    │  (via httpx)        │                       │
        │    └─────────────────────┘                       │
        │                                                  │
        │    ┌─────────────────────┐                       │
        │    │  Firecrawl SDK      │  Webpage scraping     │
        │    └─────────────────────┘                       │
        │                                                  │
        │    ┌─────────────────────┐                       │
        │    │  OpenAI Python SDK  │  GPT-4o / GPT-4o-mini │
        │    └─────────────────────┘                       │
        │                                                  │
        │    ┌─────────────────────┐                       │
        │    │  Stripe Python SDK  │  Subscription billing │
        │    └─────────────────────┘                       │
        └──────────────────────────────────────────────────┘
```

---

## 3. Project Structure

```
iqinsyt-backend/
│
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app factory, middleware, startup hooks
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                  # Pydantic Settings — reads .env
│   │   ├── security.py                # RS256 JWT signing/verification, bcrypt wrappers
│   │   ├── dependencies.py            # FastAPI Depends() — auth, DB session, rate limit
│   │   ├── exceptions.py              # Custom exception classes + FastAPI handlers
│   │   └── logging.py                 # Structured JSON logging setup
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py                    # /v1/auth/* endpoints
│   │   ├── insight.py                 # /v1/insight endpoint
│   │   ├── user.py                    # /v1/user/* endpoints
│   │   └── billing.py                 # /v1/billing/* endpoints
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py            # Registration, login, token management
│   │   ├── insight_service.py         # Orchestrates 8-step AI pipeline
│   │   ├── cache_service.py           # Redis read/write helpers
│   │   ├── vector_service.py          # Pinecone upsert/query helpers
│   │   ├── search_service.py          # Brave Search API calls (httpx)
│   │   ├── scrape_service.py          # Firecrawl SDK calls
│   │   ├── llm_service.py             # OpenAI SDK calls, failover logic
│   │   ├── compliance_service.py      # Regex + semantic scan, 3-attempt loop
│   │   ├── billing_service.py         # Stripe checkout, portal, webhook handling
│   │   └── user_service.py            # User profile, usage stats, history
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                    # SQLAlchemy DeclarativeBase + async engine
│   │   ├── user.py                    # User, RefreshToken SQLAlchemy models
│   │   ├── auth_code.py               # OneTimeAuthCode model
│   │   ├── insight.py                 # InsightRequest (history) model
│   │   └── compliance_audit.py        # ComplianceAuditLog model
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                    # Pydantic schemas: RegisterRequest, LoginRequest, etc.
│   │   ├── insight.py                 # InsightRequest, InsightResponse, InsightSections
│   │   ├── user.py                    # UserProfile, PlanResponse, UsageResponse
│   │   └── billing.py                 # CheckoutRequest, WebhookPayload, etc.
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   └── session.py                 # Async SQLAlchemy session factory
│   │
│   └── utils/
│       ├── __init__.py
│       ├── hashing.py                 # Event title hash helpers
│       └── time.py                    # UTC timestamp helpers
│
├── migrations/
│   ├── env.py                         # Alembic env config (async)
│   ├── script.py.mako                 # Alembic migration template
│   └── versions/
│       └── 0001_initial_schema.py     # First migration
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # pytest fixtures, test DB, test Redis
│   ├── test_auth.py
│   ├── test_insight.py
│   ├── test_compliance.py
│   ├── test_billing.py
│   └── test_rate_limit.py
│
├── scripts/
│   └── generate_keypair.py            # One-time RS256 key pair generation
│
├── .env.example
├── .env                               # NOT committed — see Section 14
├── pyproject.toml                     # Project metadata + dependencies
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
└── architecture_backend.md            # This file
```

---

## 4. API Endpoints — Full Specification

All endpoints are prefixed `/v1`. All request and response bodies are JSON (`Content-Type: application/json`). All authenticated endpoints require `Authorization: Bearer <access_token>` in the request header.

### 4.1 Auth Endpoints

#### `POST /v1/auth/register`

Create a new user account via email and password.

| Field | Value |
|---|---|
| Auth required | No |
| Request body | `RegisterRequest` |
| Response body | `TokenResponse` |
| Success code | `201 Created` |

```python
# schemas/auth.py
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds until access token expiry
```

| HTTP Code | Reason |
|---|---|
| `201` | Account created, tokens returned |
| `400` | Request body validation failed (missing field, weak password) |
| `409` | Email already registered |
| `422` | Pydantic validation error (invalid email format) |
| `500` | Database write failure |

---

#### `POST /v1/auth/login`

Authenticate with email and password. Returns access + refresh token pair.

| Field | Value |
|---|---|
| Auth required | No |
| Request body | `LoginRequest` |
| Response body | `TokenResponse` |
| Success code | `200 OK` |

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
```

| HTTP Code | Reason |
|---|---|
| `200` | Login successful |
| `400` | Request body validation failed |
| `401` | Email not found or password incorrect |
| `422` | Pydantic validation error |
| `429` | Too many failed login attempts (5 failures / 15 min per IP) |

---

#### `POST /v1/auth/token`

Exchange a one-time auth code (generated by the web app) for a JWT access + refresh token pair. Used exclusively by the Chrome extension to pair with an existing web session.

| Field | Value |
|---|---|
| Auth required | No |
| Request body | `AuthCodeExchangeRequest` |
| Response body | `TokenResponse` |
| Success code | `200 OK` |

```python
class AuthCodeExchangeRequest(BaseModel):
    code: str    # 8-character alphanumeric one-time code
```

| HTTP Code | Reason |
|---|---|
| `200` | Code valid, tokens returned |
| `400` | Malformed code |
| `401` | Code not found, already used, or expired (TTL: 5 minutes) |
| `422` | Pydantic validation error |

---

#### `POST /v1/auth/refresh`

Exchange a refresh token for a new access + refresh token pair (refresh token rotation).

| Field | Value |
|---|---|
| Auth required | No (refresh token in body) |
| Request body | `RefreshRequest` |
| Response body | `TokenResponse` |
| Success code | `200 OK` |

```python
class RefreshRequest(BaseModel):
    refresh_token: str
```

| HTTP Code | Reason |
|---|---|
| `200` | Rotation successful, new token pair returned |
| `401` | Refresh token invalid, expired, already used (replay detected), or revoked |
| `422` | Pydantic validation error |

---

### 4.2 User Endpoints

#### `GET /v1/user/me`

Return the authenticated user's profile.

| Field | Value |
|---|---|
| Auth required | Yes |
| Request body | None |
| Response body | `UserProfile` |
| Success code | `200 OK` |

```python
class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    plan: Literal["free", "starter", "pro"]
    created_at: datetime
    stripe_customer_id: Optional[str] = None
```

| HTTP Code | Reason |
|---|---|
| `200` | Profile returned |
| `401` | JWT missing, invalid, or expired |
| `404` | User record deleted post-auth (edge case) |

---

#### `GET /v1/user/plan`

Return the authenticated user's subscription tier and remaining monthly queries. Called by the Chrome extension before submitting an insight request.

| Field | Value |
|---|---|
| Auth required | Yes |
| Request body | None |
| Response body | `PlanResponse` |
| Success code | `200 OK` |

```python
class PlanResponse(BaseModel):
    plan: Literal["free", "starter", "pro"]
    queries_used: int
    queries_limit: int
    queries_remaining: int
    reset_at: datetime      # first day of next calendar month, UTC midnight
    subscription_active: bool
```

| HTTP Code | Reason |
|---|---|
| `200` | Plan data returned |
| `401` | JWT missing or invalid |

---

#### `POST /v1/user/auth-code`

Generate a short-lived one-time auth code that the Chrome extension can exchange via `POST /v1/auth/token`. Called by the web app when the user clicks "Connect Extension".

| Field | Value |
|---|---|
| Auth required | Yes |
| Request body | None |
| Response body | `AuthCodeResponse` |
| Success code | `201 Created` |

```python
class AuthCodeResponse(BaseModel):
    code: str           # 8-character uppercase alphanumeric, e.g. "A3FX9K2B"
    expires_at: datetime  # 5 minutes from now, UTC
```

| HTTP Code | Reason |
|---|---|
| `201` | Code generated |
| `401` | JWT missing or invalid |
| `429` | Rate limit: max 5 code generation requests per user per hour |

---

#### `GET /v1/user/usage`

Return monthly usage statistics for the authenticated user's dashboard.

| Field | Value |
|---|---|
| Auth required | Yes |
| Request body | None |
| Response body | `UsageResponse` |
| Success code | `200 OK` |

```python
class UsageResponse(BaseModel):
    plan: Literal["free", "starter", "pro"]
    current_month_queries: int
    limit: int
    cache_hits: int         # requests served from cache this month
    pipeline_runs: int      # full AI pipeline executions this month
    history_count: int      # total stored in history
```

| HTTP Code | Reason |
|---|---|
| `200` | Usage data returned |
| `401` | JWT missing or invalid |

---

#### `GET /v1/user/history`

Return paginated list of the user's recent insight requests.

| Field | Value |
|---|---|
| Auth required | Yes |
| Query params | `page: int = 1`, `page_size: int = 20` (max 100) |
| Request body | None |
| Response body | `HistoryResponse` |
| Success code | `200 OK` |

```python
class HistoryItem(BaseModel):
    request_id: str
    event_title: str
    event_source: str
    cached: bool
    generated_at: datetime
    sections: InsightSections

class HistoryResponse(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int
    page_size: int
```

| HTTP Code | Reason |
|---|---|
| `200` | History returned |
| `401` | JWT missing or invalid |
| `422` | Invalid page/page_size values |

---

### 4.3 Insight Endpoint

#### `POST /v1/insight`

Submit a detected event and receive a 7-section research result. This is the core endpoint — see Section 6 for the full pipeline.

| Field | Value |
|---|---|
| Auth required | Yes |
| Request body | `InsightRequest` |
| Response body | `InsightResponse` |
| Success code | `200 OK` |

```python
class InsightRequest(BaseModel):
    eventTitle: str = Field(min_length=1, max_length=500)
    eventSource: str = Field(min_length=1, max_length=253)
    timestamp: int           # Unix milliseconds

class InsightSections(BaseModel):
    eventSummary: str
    keyVariables: str
    historicalContext: str
    currentDrivers: str
    riskFactors: str
    dataConfidence: str
    dataGaps: str

class InsightResponse(BaseModel):
    requestId: str
    cached: bool
    cachedAt: Optional[str] = None    # ISO 8601 timestamp string if cached
    sections: InsightSections
    dataRetrievalAvailable: bool
    generatedAt: str                  # ISO 8601 timestamp string
```

| HTTP Code | Reason |
|---|---|
| `200` | Research result returned (cached or freshly generated) |
| `400` | eventTitle empty or exceeds 500 characters |
| `401` | JWT missing, invalid, or expired |
| `402` | Subscription inactive or payment failed |
| `422` | Pydantic validation error |
| `429` | Monthly query limit exceeded for the user's plan tier |
| `503` | All LLM providers unavailable and no cached fallback exists |

---

### 4.4 Billing Endpoints

#### `POST /v1/billing/checkout`

Create a Stripe Checkout session for a plan upgrade. Returns the session URL to redirect the user to.

| Field | Value |
|---|---|
| Auth required | Yes |
| Request body | `CheckoutRequest` |
| Response body | `CheckoutResponse` |
| Success code | `200 OK` |

```python
class CheckoutRequest(BaseModel):
    plan: Literal["starter", "pro"]
    success_url: str      # redirect URL after successful payment
    cancel_url: str       # redirect URL if user cancels

class CheckoutResponse(BaseModel):
    checkout_url: str     # Stripe-hosted checkout page URL
    session_id: str
```

| HTTP Code | Reason |
|---|---|
| `200` | Checkout session created |
| `400` | Invalid plan name, or user already on this plan |
| `401` | JWT missing or invalid |
| `500` | Stripe API error |

---

#### `POST /v1/billing/portal`

Create a Stripe Customer Portal session for subscription management (cancel, update payment method).

| Field | Value |
|---|---|
| Auth required | Yes |
| Request body | `PortalRequest` |
| Response body | `PortalResponse` |
| Success code | `200 OK` |

```python
class PortalRequest(BaseModel):
    return_url: str       # redirect URL when user closes the portal

class PortalResponse(BaseModel):
    portal_url: str
```

| HTTP Code | Reason |
|---|---|
| `200` | Portal session created |
| `401` | JWT missing or invalid |
| `404` | No Stripe customer record found for this user |
| `500` | Stripe API error |

---

#### `POST /v1/billing/webhook`

Receive Stripe webhook events (subscription created, updated, deleted, payment failed). This endpoint must be excluded from JWT auth middleware — it uses Stripe signature verification instead.

| Field | Value |
|---|---|
| Auth required | No (Stripe signature in `Stripe-Signature` header) |
| Request body | Raw bytes (Stripe event payload) |
| Response body | `{"received": true}` |
| Success code | `200 OK` |

Handled Stripe events:

| Stripe Event | Action |
|---|---|
| `customer.subscription.created` | Set user plan, store `stripe_subscription_id` |
| `customer.subscription.updated` | Update user plan tier |
| `customer.subscription.deleted` | Downgrade user to `free` plan |
| `invoice.payment_failed` | Set `subscription_active = false`, notify user |
| `invoice.payment_succeeded` | Set `subscription_active = true`, reset monthly query counter |

| HTTP Code | Reason |
|---|---|
| `200` | Event received and processed (always return 200 to Stripe) |
| `400` | Stripe signature verification failed — reject silently |

---

### 4.5 Health Endpoint

#### `GET /health`

Liveness and readiness probe for Docker/Railway/Render health checks. No auth required.

```python
class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: Literal["ok", "error"]
    redis: Literal["ok", "error"]
    version: str
```

| HTTP Code | Reason |
|---|---|
| `200` | Server is up (db and redis may still report "error" in body) |

---

## 5. Auth Module

### 5.1 Registration Flow

```
POST /v1/auth/register
    │
    ├── Validate RegisterRequest (Pydantic)
    ├── Check email uniqueness in PostgreSQL
    ├── Hash password with bcrypt (cost factor 12)
    ├── INSERT user row (plan = "free", created_at = now())
    ├── Create Stripe Customer (stripe.Customer.create)
    │     → store stripe_customer_id on user row
    ├── Generate access token (RS256 JWT, 15 min TTL)
    ├── Generate refresh token (opaque 64-byte random hex, 30 days TTL)
    ├── INSERT refresh token row (hashed token, user_id, expires_at)
    └── Return TokenResponse
```

### 5.2 Login Flow

```
POST /v1/auth/login
    │
    ├── Look up user by email
    ├── Verify bcrypt hash (passlib.context.verify)
    ├── On failure: increment failed_attempts counter in Redis (key: login_fail:{email})
    │     → if attempts >= 5 in 15 min window: return 429
    ├── On success: reset Redis counter
    ├── Generate new access token + refresh token
    ├── INSERT refresh token row (invalidate old tokens if single-session mode)
    └── Return TokenResponse
```

### 5.3 RS256 JWT — Signing and Verification

RS256 uses an asymmetric key pair: the private key signs tokens, the public key verifies them. This allows the Chrome extension (or any consumer) to verify tokens without ever having access to the private key.

**Key generation (run once, store in environment):**

```python
# scripts/generate_keypair.py
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode()

public_pem = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()

print("JWT_PRIVATE_KEY=", repr(private_pem))
print("JWT_PUBLIC_KEY=", repr(public_pem))
```

Store the PEM strings in `.env` with literal `\n` encoded as `\\n` (or use multi-line env var syntax on Railway/Render).

**Token creation:**

```python
# app/core/security.py
from jose import jwt
from datetime import datetime, timedelta, timezone
from app.core.config import settings

ACCESS_TOKEN_EXPIRE_MINUTES = 15
ALGORITHM = "RS256"

def create_access_token(user_id: str, plan: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "plan": plan,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm=ALGORITHM)

def verify_access_token(token: str) -> dict:
    """Raises jose.JWTError on invalid/expired token."""
    return jwt.decode(token, settings.JWT_PUBLIC_KEY, algorithms=[ALGORITHM])
```

**FastAPI dependency for protected endpoints:**

```python
# app/core/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from app.core.security import verify_access_token
from app.db.session import get_db

bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = verify_access_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

### 5.4 Refresh Token Rotation with Replay Attack Detection

Refresh tokens are opaque 64-byte random hex strings stored **hashed** in PostgreSQL. On each refresh:

1. The client sends their current refresh token.
2. The server looks up the hash in `refresh_tokens` table.
3. If the token row has `used = True` — a replay attack is detected. Immediately revoke **all** refresh tokens for that `user_id`.
4. If valid and unused: mark the row as `used = True`, issue a new access + refresh token pair, insert a new refresh token row.
5. The old row is never deleted — it stays with `used = True` for the replay detection audit trail.

```python
# app/services/auth_service.py
import secrets
import hashlib

def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, hashed_token). Store only the hash."""
    raw = secrets.token_hex(64)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed

async def rotate_refresh_token(
    raw_token: str,
    db: AsyncSession,
) -> TokenResponse:
    hashed = hashlib.sha256(raw_token.encode()).hexdigest()
    stmt = select(RefreshToken).where(RefreshToken.token_hash == hashed)
    result = await db.execute(stmt)
    token_row = result.scalar_one_or_none()

    if token_row is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if token_row.used:
        # Replay attack detected — revoke all tokens for this user
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == token_row.user_id)
            .values(revoked=True)
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Refresh token already used")

    if token_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    if token_row.revoked:
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    # Mark old token used
    token_row.used = True
    await db.flush()

    # Issue new pair
    user = await db.get(User, token_row.user_id)
    new_access = create_access_token(str(user.id), user.plan)
    new_raw, new_hash = generate_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    await db.commit()
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_raw,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
```

### 5.5 One-Time Auth Code — Generation and Exchange

The web app generates a short-lived 8-character alphanumeric code stored in Redis. The Chrome extension exchanges it for a full token pair.

```python
# app/services/auth_service.py
import secrets
import string

AUTH_CODE_TTL_SECONDS = 300   # 5 minutes
AUTH_CODE_PREFIX = "auth_code:"

def generate_auth_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))

async def create_auth_code(user_id: str, redis: Redis) -> AuthCodeResponse:
    code = generate_auth_code()
    key = f"{AUTH_CODE_PREFIX}{code}"
    await redis.setex(key, AUTH_CODE_TTL_SECONDS, user_id)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=AUTH_CODE_TTL_SECONDS)
    return AuthCodeResponse(code=code, expires_at=expires_at)

async def exchange_auth_code(
    code: str,
    redis: Redis,
    db: AsyncSession,
) -> TokenResponse:
    key = f"{AUTH_CODE_PREFIX}{code}"
    user_id = await redis.getdel(key)   # atomic get + delete (single use)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired auth code")
    user = await db.get(User, user_id.decode())
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    access = create_access_token(str(user.id), user.plan)
    raw_refresh, hashed_refresh = generate_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    await db.commit()
    return TokenResponse(
        access_token=access,
        refresh_token=raw_refresh,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
```

---

## 6. Insight Module — The AI Pipeline

Every call to `POST /v1/insight` passes through 8 discrete async steps in `app/services/insight_service.py`. Each step is a separate async function to make them independently testable and replaceable.

### Pipeline Overview

```
POST /v1/insight (InsightRequest)
    │
    ├── Step 1: JWT validated (FastAPI dependency — before router)
    │
    ├── Step 2: Redis cache lookup
    │              HIT  ──────────────────────────────────────────► return InsightResponse (cached=True)
    │              MISS ──► continue
    │
    ├── Step 3: Pinecone semantic match
    │              MATCH (cosine > 0.92) ──────────────────────────► return InsightResponse (cached=True)
    │              NO MATCH ──► continue
    │
    ├── Step 4: Brave Search + Firecrawl
    │              Firecrawl fails ──► set dataRetrievalAvailable=False, continue
    │
    ├── Step 5: Prompt assembly
    │
    ├── Step 6: LLM call (GPT-4o-mini or GPT-4o based on plan)
    │              Timeout/failure ──► failover (Step 6a)
    │
    ├── Step 7: Neutrality & Compliance scan
    │              FAIL ──► re-queue LLM (max 3 total attempts)
    │              3rd FAIL ──► return partial output
    │
    ├── Step 8: Cache in Redis + upsert Pinecone embedding
    │
    └── return InsightResponse (cached=False)
```

### Step 1 — JWT Validation

Handled by the `get_current_user` FastAPI dependency injected into the router. By the time the service function is called, `current_user: User` is already populated. The plan tier (`current_user.plan`) is extracted here and passed through the pipeline to select the correct LLM model.

### Step 2 — Redis Cache Lookup

```python
# app/services/cache_service.py
import hashlib
import json
from datetime import date

CACHE_PREFIX = "insight"
CACHE_TTL_SECONDS = 4 * 60 * 60   # 4 hours

def make_cache_key(event_title: str) -> str:
    today = date.today().isoformat()          # e.g. "2026-04-02"
    normalized = event_title.strip().lower()
    title_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"{CACHE_PREFIX}:{title_hash}:{today}"

async def get_cached_insight(event_title: str, redis: Redis) -> dict | None:
    key = make_cache_key(event_title)
    raw = await redis.get(key)
    if raw is None:
        return None
    return json.loads(raw)

async def set_cached_insight(event_title: str, payload: dict, redis: Redis) -> None:
    key = make_cache_key(event_title)
    await redis.setex(key, CACHE_TTL_SECONDS, json.dumps(payload))
```

On a cache hit, return immediately with `cached=True` and `cachedAt` set to the original `generatedAt` timestamp stored in the cached payload. The Redis lookup adds ~1–2ms latency.

### Step 3 — Pinecone Semantic Match

The embedding for the incoming `eventTitle` is generated using `text-embedding-3-small` (OpenAI). This model produces 1536-dimensional vectors. The vector is queried against the Pinecone index to find semantically similar prior queries.

```python
# app/services/vector_service.py
from openai import AsyncOpenAI
from pinecone import Pinecone

SIMILARITY_THRESHOLD = 0.92
EMBEDDING_MODEL = "text-embedding-3-small"

async def get_embedding(text: str, openai_client: AsyncOpenAI) -> list[float]:
    response = await openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text.strip().lower(),
    )
    return response.data[0].embedding

async def semantic_match(
    event_title: str,
    openai_client: AsyncOpenAI,
    pinecone_index,
) -> dict | None:
    vector = await get_embedding(event_title, openai_client)
    result = pinecone_index.query(
        vector=vector,
        top_k=1,
        include_metadata=True,
    )
    if not result.matches:
        return None
    top = result.matches[0]
    if top.score >= SIMILARITY_THRESHOLD:
        return top.metadata   # contains the serialised InsightSections
    return None
```

The 0.92 cosine similarity threshold is calibrated so that "Manchester City vs Arsenal" and "Arsenal v Manchester City" match each other (same event, different phrasing), but "Arsenal vs Chelsea" does not match "Arsenal vs Liverpool". See Section 10 for full rationale.

### Step 4 — Brave Search + Firecrawl Scraping

```python
# app/services/search_service.py
import httpx
from app.core.config import settings

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

async def brave_search(query: str, count: int = 5) -> list[dict]:
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(
            BRAVE_SEARCH_URL,
            headers={"Accept": "application/json", "X-Subscription-Token": settings.BRAVE_API_KEY},
            params={"q": query, "count": count, "search_lang": "en"},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("web", {}).get("results", [])

async def gather_search_results(event_title: str) -> list[dict]:
    queries = [
        f"{event_title} news",
        f"{event_title} recent form analysis",
        f"{event_title} preview",
    ]
    results = []
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(brave_search(q, count=3)) for q in queries]
    for task in tasks:
        results.extend(task.result())
    # Deduplicate by URL
    seen = set()
    unique = []
    for r in results:
        url = r.get("url", "")
        if url not in seen:
            seen.add(url)
            unique.append(r)
    return unique[:6]   # cap at 6 results to control token budget
```

```python
# app/services/scrape_service.py
from firecrawl import FirecrawlApp
from app.core.config import settings

async def scrape_urls(urls: list[str]) -> tuple[str, bool]:
    """
    Returns (scraped_text, data_retrieval_available).
    If Firecrawl fails entirely, returns ("", False).
    """
    app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
    texts = []
    try:
        for url in urls[:3]:    # scrape at most 3 pages (avg 3 credits/session)
            result = app.scrape_url(url, params={"formats": ["markdown"]})
            if result.get("markdown"):
                texts.append(result["markdown"][:3000])   # cap per-page content
    except Exception:
        return "", False
    if not texts:
        return "", False
    return "\n\n---\n\n".join(texts), True
```

### Step 5 — Prompt Assembly

```python
# app/services/insight_service.py

SYSTEM_PROMPT = """You are a neutral research analyst. Your sole role is to surface \
factual, structured information about the event provided. You must not make predictions, \
issue recommendations, suggest probabilities, rank outcomes by likelihood, or use \
persuasive or emotionally charged language of any kind. Every section must be written \
in plain, balanced, factual prose."""

SECTION_INSTRUCTIONS = """Return your response as a JSON object with exactly these keys:
{
  "eventSummary": "...",
  "keyVariables": "...",
  "historicalContext": "...",
  "currentDrivers": "...",
  "riskFactors": "...",
  "dataConfidence": "...",
  "dataGaps": "..."
}

Definitions:
- eventSummary: What the event is, who/what is involved, when and where it takes place.
- keyVariables: Objective factors that are relevant to the event (form, fitness, conditions, etc.).
- historicalContext: Past encounters, trends, or statistical record — stated as facts.
- currentDrivers: Recent developments, news, or circumstances relevant to this event.
- riskFactors: Uncertainties, unknowns, or factors that could change outcomes — neutral.
- dataConfidence: Assess the quality and recency of available data. No predictions.
- dataGaps: Identify what information is missing or unavailable."""

NEGATIVE_CONSTRAINTS = """DO NOT use any of the following:
- Predictive language: "likely", "expected to", "odds favour", "probability of", "projected", "forecast", "anticipated"
- Recommendation language: "consider backing", "worth backing", "recommended", "favourable", "strong case for"
- Emotionally charged phrases: "dominant", "unstoppable", "inevitably", "sure to", "guaranteed"
- Any language that implies one outcome is more probable than another."""

def assemble_prompt(
    event_title: str,
    event_source: str,
    research_context: str,
) -> list[dict]:
    user_content = f"""Event: {event_title}
Detected on: {event_source}

Research context:
{research_context if research_context else "[No external data available — use only general knowledge.]"}

{SECTION_INSTRUCTIONS}

{NEGATIVE_CONSTRAINTS}"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
```

**Token budget:** The system prompt is ~200 tokens. The research context is capped at 9,000 tokens (3 pages × 3,000 tokens). The section instructions and constraints add ~400 tokens. Total input budget: ~10,000 tokens, well within GPT-4o-mini's 128k context window.

### Step 6 — LLM Call

```python
# app/services/llm_service.py
from openai import AsyncOpenAI
from app.core.config import settings

MODEL_MAP = {
    "free":    "gpt-4o-mini",
    "starter": "gpt-4o-mini",
    "pro":     "gpt-4o",
}
LLM_TIMEOUT_SECONDS = 8.0

async def call_llm(
    messages: list[dict],
    plan: str,
    openai_client: AsyncOpenAI,
    attempt: int = 1,
) -> dict | None:
    """
    Returns parsed InsightSections dict, or None on failure.
    attempt is 1-indexed. On attempt 1, use plan model.
    On attempt 2+, use gpt-4o regardless.
    """
    model = MODEL_MAP[plan] if attempt == 1 else "gpt-4o"
    try:
        response = await asyncio.wait_for(
            openai_client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=2000,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None
```

**LLM Failover chain:**

```
Attempt 1: plan model (gpt-4o-mini or gpt-4o), timeout 8s
    ↓ None returned
Attempt 2: gpt-4o, timeout 8s
    ↓ None returned
Attempt 3: gpt-4o, timeout 8s
    ↓ None returned
Serve most recent Redis cached result for this event (any date)
    ↓ no cached result exists
Return 503 with detail="Insight temporarily unavailable"
```

Note: Attempts 2 and 3 happen only if compliance fails, not if the LLM itself fails. If the LLM itself returns `None` twice (both models down), fall back to cache immediately.

### Step 7 — Neutrality & Compliance Layer

See Section 7 for the full compliance implementation. This step wraps the LLM call in a retry loop. If all 3 attempts fail compliance, the sections that individually passed are returned (per-section quarantine).

### Step 8 — Cache Write + Pinecone Upsert

```python
# app/services/insight_service.py

async def store_result(
    event_title: str,
    request_id: str,
    sections: InsightSections,
    data_retrieval_available: bool,
    generated_at: str,
    redis: Redis,
    pinecone_index,
    openai_client: AsyncOpenAI,
) -> None:
    payload = {
        "requestId": request_id,
        "cached": True,
        "cachedAt": generated_at,
        "sections": sections.model_dump(),
        "dataRetrievalAvailable": data_retrieval_available,
        "generatedAt": generated_at,
    }
    # Write to Redis
    await set_cached_insight(event_title, payload, redis)

    # Upsert to Pinecone (non-blocking — fire and forget is acceptable here)
    vector = await get_embedding(event_title, openai_client)
    pinecone_index.upsert(vectors=[{
        "id": request_id,
        "values": vector,
        "metadata": {
            "event_title": event_title,
            "generated_at": generated_at,
            "sections": json.dumps(sections.model_dump()),
            "data_retrieval_available": data_retrieval_available,
        },
    }])
```

---

## 7. Neutrality & Compliance Module

The compliance layer is **mandatory and non-bypassable**. Every LLM response passes through it before it is cached or returned to any client.

### 7.1 Blocked Patterns — Full Regex List

```python
# app/services/compliance_service.py
import re

COMPLIANCE_PATTERNS: list[re.Pattern] = [
    # Predictive language
    re.compile(r"\blikely\s+to\s+(win|lose|score|succeed|fail)\b", re.IGNORECASE),
    re.compile(r"\bexpected\s+to\b", re.IGNORECASE),
    re.compile(r"\bodds\s+favour\b", re.IGNORECASE),
    re.compile(r"\bprobability\s+of\b", re.IGNORECASE),
    re.compile(r"\bprojected\s+to\b", re.IGNORECASE),
    re.compile(r"\bforecast(ed)?\s+to\b", re.IGNORECASE),
    re.compile(r"\banticipated\s+to\b", re.IGNORECASE),
    re.compile(r"\bpredicted\s+to\b", re.IGNORECASE),
    re.compile(r"\bmore\s+likely\b", re.IGNORECASE),
    re.compile(r"\bless\s+likely\b", re.IGNORECASE),
    re.compile(r"\bhigher\s+chance\b", re.IGNORECASE),
    re.compile(r"\blower\s+chance\b", re.IGNORECASE),
    re.compile(r"\b\d+%\s+chance\b", re.IGNORECASE),
    re.compile(r"\bwill\s+(almost\s+certainly|definitely|probably)\b", re.IGNORECASE),

    # Recommendation language
    re.compile(r"\brecommended\s+bet\b", re.IGNORECASE),
    re.compile(r"\bconsider\s+backing\b", re.IGNORECASE),
    re.compile(r"\bworth\s+backing\b", re.IGNORECASE),
    re.compile(r"\bgood\s+pick\b", re.IGNORECASE),
    re.compile(r"\bstrong\s+case\s+for\b", re.IGNORECASE),
    re.compile(r"\bfavou?rable\s+(pick|choice|bet|option)\b", re.IGNORECASE),
    re.compile(r"\bback\s+(them|him|her|it)\b", re.IGNORECASE),

    # Emotionally charged / absolute language
    re.compile(r"\bdominant\s+(form|side|team|performer)\b", re.IGNORECASE),
    re.compile(r"\bunstoppable\b", re.IGNORECASE),
    re.compile(r"\binevitably\b", re.IGNORECASE),
    re.compile(r"\bsure\s+to\b", re.IGNORECASE),
    re.compile(r"\bguaranteed\s+to\b", re.IGNORECASE),
    re.compile(r"\bcertain\s+to\b", re.IGNORECASE),
    re.compile(r"\bbound\s+to\b", re.IGNORECASE),

    # Outcome ranking
    re.compile(r"\bfavou?rite\b", re.IGNORECASE),       # "favourite to win"
    re.compile(r"\bunderdog\b", re.IGNORECASE),
    re.compile(r"\bhas\s+the\s+(edge|advantage|upper\s+hand)\b", re.IGNORECASE),
    re.compile(r"\bstronger\s+(team|side|performer)\b", re.IGNORECASE),
    re.compile(r"\bweaker\s+(team|side|performer)\b", re.IGNORECASE),
]
```

### 7.2 Scan Function

```python
def scan_section(text: str) -> list[str]:
    """
    Returns list of triggered pattern strings. Empty list = PASS.
    """
    triggers = []
    for pattern in COMPLIANCE_PATTERNS:
        match = pattern.search(text)
        if match:
            triggers.append(match.group(0))
    return triggers

def scan_sections(sections: dict) -> dict[str, list[str]]:
    """
    Returns {section_name: [triggered_phrases]} for all sections.
    A section is compliant if its list is empty.
    """
    return {key: scan_section(value) for key, value in sections.items()}
```

### 7.3 The 3-Attempt Loop with Per-Section Quarantine

```python
# app/services/compliance_service.py

UNAVAILABLE_PLACEHOLDER = "[Section unavailable — compliance filter applied]"

async def run_compliant_pipeline(
    messages: list[dict],
    plan: str,
    openai_client: AsyncOpenAI,
    request_id: str,
    event_title: str,
    db: AsyncSession,
) -> tuple[dict, bool]:
    """
    Returns (sections_dict, fully_compliant: bool).
    Runs up to 3 LLM attempts. After 3 failures, returns per-section quarantine result.
    """
    all_attempts: list[dict | None] = []

    for attempt in range(1, 4):
        raw = await call_llm(messages, plan, openai_client, attempt)
        if raw is None:
            continue   # LLM failure — will handle below
        all_attempts.append(raw)
        violations = scan_sections(raw)
        has_violations = any(v for v in violations.values())

        if not has_violations:
            # Full compliance — return immediately
            return raw, True

        # Log the failed attempt
        await log_compliance_intervention(
            request_id=request_id,
            event_title=event_title,
            attempt=attempt,
            violations=violations,
            action="regenerate" if attempt < 3 else "quarantine",
            db=db,
        )

    # All 3 attempts exhausted — apply per-section quarantine
    if not all_attempts:
        # LLM itself failed — return all placeholders
        sections = {k: UNAVAILABLE_PLACEHOLDER for k in InsightSections.model_fields}
        return sections, False

    # Use the last successful LLM response, zero out non-compliant sections
    best = all_attempts[-1]
    violations = scan_sections(best)
    quarantined = {}
    for section, triggers in violations.items():
        if triggers:
            quarantined[section] = UNAVAILABLE_PLACEHOLDER
        else:
            quarantined[section] = best[section]
    return quarantined, False
```

### 7.4 Audit Logging to PostgreSQL

Every compliance intervention is written to the `compliance_audit_logs` table (see Section 8.5).

```python
async def log_compliance_intervention(
    request_id: str,
    event_title: str,
    attempt: int,
    violations: dict[str, list[str]],
    action: str,   # "regenerate" | "quarantine"
    db: AsyncSession,
) -> None:
    log = ComplianceAuditLog(
        request_id=request_id,
        event_title=event_title,
        attempt_number=attempt,
        triggered_patterns=json.dumps(violations),
        action=action,
        logged_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.commit()
```

Audit logs are **never deleted**. They are append-only and serve as the compliance evidence trail for regulatory review.

---

## 8. Database Schema

### 8.1 SQLAlchemy Base

```python
# app/models/base.py
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    pass

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

### 8.2 User Model

```python
# app/models/user.py
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(60), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    subscription_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    queries_used_this_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 8.3 Refresh Token Model

```python
# app/models/user.py (continued)
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=datetime.utcnow)
```

### 8.4 Insight History Model

```python
# app/models/insight.py
class InsightHistory(Base):
    __tablename__ = "insight_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_title: Mapped[str] = mapped_column(String(500), nullable=False)
    event_source: Mapped[str] = mapped_column(String(253), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_retrieval_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sections_json: Mapped[str] = mapped_column(String, nullable=False)   # JSON string
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=datetime.utcnow)
```

### 8.5 Compliance Audit Log Model

```python
# app/models/compliance_audit.py
class ComplianceAuditLog(Base):
    __tablename__ = "compliance_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_title: Mapped[str] = mapped_column(String(500), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    triggered_patterns: Mapped[str] = mapped_column(String, nullable=False)  # JSON: {section: [phrases]}
    action: Mapped[str] = mapped_column(String(20), nullable=False)           # "regenerate" | "quarantine"
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

### 8.6 Raw SQL — All Tables with Indexes

```sql
-- users
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(320) NOT NULL UNIQUE,
    hashed_password VARCHAR(60) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    plan VARCHAR(20) NOT NULL DEFAULT 'free',
    subscription_active BOOLEAN NOT NULL DEFAULT FALSE,
    stripe_customer_id VARCHAR(100),
    stripe_subscription_id VARCHAR(100),
    queries_used_this_month INTEGER NOT NULL DEFAULT 0,
    usage_reset_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_stripe_customer_id ON users (stripe_customer_id);

-- refresh_tokens
CREATE TABLE refresh_tokens (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens (token_hash);

-- insight_history
CREATE TABLE insight_history (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    event_title VARCHAR(500) NOT NULL,
    event_source VARCHAR(253) NOT NULL,
    request_id VARCHAR(36) NOT NULL UNIQUE,
    cached BOOLEAN NOT NULL DEFAULT FALSE,
    data_retrieval_available BOOLEAN NOT NULL DEFAULT TRUE,
    sections_json TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_insight_history_user_id ON insight_history (user_id);
CREATE INDEX idx_insight_history_user_id_created_at ON insight_history (user_id, created_at DESC);

-- compliance_audit_logs
CREATE TABLE compliance_audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    request_id VARCHAR(36) NOT NULL,
    event_title VARCHAR(500) NOT NULL,
    attempt_number INTEGER NOT NULL,
    triggered_patterns TEXT NOT NULL,
    action VARCHAR(20) NOT NULL,
    logged_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_compliance_audit_request_id ON compliance_audit_logs (request_id);
CREATE INDEX idx_compliance_audit_logged_at ON compliance_audit_logs (logged_at DESC);
```

---

## 9. Redis Schema

Redis is used for three purposes: response caching, rate limit counters, and one-time auth codes. All keys use a structured prefix pattern to avoid collisions.

| Key Pattern | TTL | Data Type | Contents |
|---|---|---|---|
| `insight:{title_hash}:{date}` | 4 hours (14,400s) | String (JSON) | Full `InsightResponse` payload as JSON string |
| `rate:{user_id}:{YYYY-MM}` | Until end of month + 1 day | String (integer) | Monthly query count for the user |
| `auth_code:{CODE}` | 5 minutes (300s) | String | `user_id` value (UTF-8 encoded) |
| `login_fail:{email_hash}` | 15 minutes (900s) | String (integer) | Count of failed login attempts |
| `rate_limit_ip:{ip}:{endpoint}` | 15 minutes (900s) | String (integer) | Failed login attempts per IP |

**Key details:**

- `insight` cache key: `title_hash` is the first 16 hex chars of `SHA-256(event_title.strip().lower())`. Appending the ISO date (`YYYY-MM-DD`) ensures cache invalidation at midnight UTC.
- `rate:{user_id}:{YYYY-MM}`: The month component acts as a natural key partition. On the first request of a new month, the old key has expired and a new one is created with `INCR` + `EXPIREAT` set to midnight UTC on the first day of the following month.
- `auth_code:{CODE}`: Uses `GETDEL` on exchange — atomic get + delete in a single command. This guarantees single-use semantics without a separate `DEL` call.

**Monthly counter implementation:**

```python
# app/services/cache_service.py
from calendar import monthrange
from datetime import datetime, timezone

async def increment_query_counter(user_id: str, redis: Redis) -> int:
    """Increments counter and sets expiry to end of current month. Returns new count."""
    now = datetime.now(timezone.utc)
    key = f"rate:{user_id}:{now.strftime('%Y-%m')}"
    pipe = redis.pipeline()
    pipe.incr(key)
    # Calculate seconds until midnight UTC on first day of next month
    if now.month == 12:
        next_month_start = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month_start = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    ttl = int((next_month_start - now).total_seconds()) + 86400  # +1 day buffer
    pipe.expire(key, ttl)
    results = await pipe.execute()
    return results[0]   # new counter value
```

---

## 10. Pinecone Schema

### 10.1 Index Configuration

| Setting | Value |
|---|---|
| Index name | `iqinsyt-insights` |
| Dimensions | `1536` |
| Metric | `cosine` |
| Pod type | `p1.x1` (starter) or serverless (recommended) |
| Environment | `us-east-1-aws` (or as per Pinecone account region) |
| Embedding model | `text-embedding-3-small` (OpenAI) |

Use serverless Pinecone for simplicity at launch — no pod sizing decisions, pay-per-query.

**Index creation (run once at setup):**

```python
# scripts/setup_pinecone.py
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key=settings.PINECONE_API_KEY)
pc.create_index(
    name="iqinsyt-insights",
    dimension=1536,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
)
```

### 10.2 Vector Record Structure

Each upserted record has this structure:

```python
{
    "id": "<request_id>",            # UUID4 string — unique per pipeline run
    "values": [0.023, -0.441, ...],  # 1536-dimensional float vector
    "metadata": {
        "event_title": "Manchester City vs Arsenal",
        "generated_at": "2026-04-02T14:33:00Z",    # ISO 8601
        "sections": "{\"eventSummary\": \"...\", ...}",  # JSON-serialised InsightSections
        "data_retrieval_available": True,
    }
}
```

All metadata fields are stored as strings or booleans (Pinecone metadata value types). The `sections` field is a JSON string because Pinecone does not support nested objects in metadata.

### 10.3 Query Pattern

```python
result = pinecone_index.query(
    vector=embedding_vector,
    top_k=1,
    include_metadata=True,
)
```

Only `top_k=1` is requested — we want the single best match. The `include_metadata=True` flag returns the stored sections directly, avoiding a PostgreSQL lookup.

### 10.4 Similarity Threshold Rationale — 0.92

The 0.92 cosine similarity threshold is chosen because:

- At 0.92+: "Man City vs Arsenal" and "Arsenal vs Man City" score ~0.95 — same event, different phrasing. These should match.
- At 0.92+: "Arsenal vs Chelsea" and "Arsenal vs Man City" score ~0.87 — different events. These must NOT match.
- At 0.92+: "Man City vs Arsenal (FA Cup)" and "Man City vs Arsenal (Premier League)" score ~0.91 — same teams, different competition. This is a borderline case; at 0.92 they will NOT match, which is the safer behaviour (run fresh pipeline, different competition context).
- `text-embedding-3-small` produces highly consistent vectors for paraphrased text, making 0.92 a reliable threshold that avoids false positives.

If semantic match quality degrades in production, raise the threshold to 0.94. Do not lower it below 0.90 — cross-event false positives are worse than cache misses.

---

## 11. Rate Limiting

### 11.1 Limits Per Plan Tier

| Plan | Monthly Query Limit | Request Limit (burst) |
|---|---|---|
| `free` | 10 queries / month | 2 requests / minute |
| `starter` | 100 queries / month | 10 requests / minute |
| `pro` | 500 queries / month | 30 requests / minute |

Additionally, login attempts are rate-limited regardless of plan: 5 failed attempts per email per 15 minutes (per-IP secondary limit: 20 failed attempts per IP per 15 minutes).

### 11.2 FastAPI Dependency Implementation

Rate limiting is implemented as a FastAPI dependency that wraps Redis counter checks. It runs **after** JWT validation so that `user_id` and `plan` are available.

```python
# app/core/dependencies.py
from fastapi import Depends, HTTPException, Request, status

PLAN_MONTHLY_LIMITS = {"free": 10, "starter": 100, "pro": 500}
PLAN_BURST_LIMITS = {"free": 2, "starter": 10, "pro": 30}  # per minute

async def check_monthly_rate_limit(
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> User:
    """Raises 429 if user has exhausted monthly query limit."""
    limit = PLAN_MONTHLY_LIMITS[current_user.plan]
    now = datetime.now(timezone.utc)
    key = f"rate:{current_user.id}:{now.strftime('%Y-%m')}"
    count = await redis.get(key)
    if count is not None and int(count) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly query limit of {limit} reached for {current_user.plan} plan.",
            headers={"Retry-After": str(seconds_until_month_end())},
        )
    return current_user

async def check_burst_rate_limit(
    request: Request,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> User:
    """Raises 429 if user exceeds per-minute burst limit."""
    burst_limit = PLAN_BURST_LIMITS[current_user.plan]
    now = datetime.now(timezone.utc)
    minute_key = f"burst:{current_user.id}:{now.strftime('%Y-%m-%dT%H:%M')}"
    pipe = redis.pipeline()
    pipe.incr(minute_key)
    pipe.expire(minute_key, 90)   # 90s TTL, covers current + next minute window
    results = await pipe.execute()
    count = results[0]
    if count > burst_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait before retrying.",
            headers={"Retry-After": "60"},
        )
    return current_user
```

**Router usage:**

```python
# app/routers/insight.py
@router.post("/insight", response_model=InsightResponse)
async def create_insight(
    body: InsightRequest,
    user: User = Depends(check_burst_rate_limit),   # burst check (also calls monthly check internally)
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    # Monthly check is also applied by incrementing counter after successful pipeline run
    ...
```

The monthly counter is incremented **after** a successful pipeline run (not at request entry), so failed or cached requests do not consume quota. Cache hits do count against quota — a query is a query, regardless of whether it was served from cache.

---

## 12. Caching Strategy

### 12.1 Priority Order

Every incoming `POST /v1/insight` request is served through a three-tier cache hierarchy:

```
Tier 1: Redis (exact match)
    Key: insight:{sha256(title.lower())[:16]}:{today_iso}
    Latency: ~1–2ms
    Serves: Identical or near-identical event titles, same calendar day
    ↓ MISS

Tier 2: Pinecone (semantic match)
    Query: cosine similarity > 0.92 on title embedding
    Latency: ~50–100ms
    Serves: Same event with different phrasing (e.g. "vs" vs "v", name order swap)
    ↓ MISS

Tier 3: Full AI pipeline
    Steps 4–8 (Brave + Firecrawl + LLM + Compliance)
    Latency: 2–5 seconds
    Writes result to Redis and Pinecone after completion
```

### 12.2 Write Strategy

Results are written to both Redis and Pinecone **after** the compliance check passes. If compliance produces a partial result (some sections quarantined), the partial result is still cached — but with the quarantined sections containing the placeholder string. This ensures subsequent cache hits return consistently formatted output.

Pinecone upsert failures are non-fatal — log the error and continue. Redis write failures are also non-fatal at the response layer — the response is still returned to the client; only the cache miss rate increases temporarily.

### 12.3 TTL Policy

| Cache Layer | TTL | Rationale |
|---|---|---|
| Redis insight | 4 hours | Keeps results fresh within a match day; stale results after significant news events. |
| Pinecone vectors | No expiry (persistent) | Semantic index grows over time. Old events are naturally not queried. Prune annually via `delete_many` for events older than 90 days. |
| Auth codes (Redis) | 5 minutes | Short window minimises attack surface for code interception. |
| Monthly rate counters (Redis) | Until first of next month + 1 day | Aligned to billing cycles. |
| Login fail counters (Redis) | 15 minutes | Sliding window for brute-force protection. |

### 12.4 Cache Invalidation

There is no explicit cache invalidation for insight results. The 4-hour TTL is the invalidation mechanism. If a result must be manually invalidated (e.g., factually incorrect data was cached), use `redis.delete(make_cache_key(event_title))` directly.

---

## 13. Error Handling

### 13.1 Standard Error Response Shape

All API errors return a consistent JSON envelope:

```python
# app/schemas/errors.py (also used in exception handlers)
class ErrorResponse(BaseModel):
    error: str         # machine-readable code, e.g. "INVALID_TOKEN"
    message: str       # human-readable description
    request_id: str    # UUID from X-Request-ID header (injected by middleware)
    timestamp: str     # ISO 8601 UTC
```

Example:

```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Monthly query limit of 10 reached for free plan.",
  "request_id": "a1b2c3d4-...",
  "timestamp": "2026-04-02T14:33:00Z"
}
```

### 13.2 HTTP Status Code Mapping

| Status Code | Error Code | When |
|---|---|---|
| `400 Bad Request` | `VALIDATION_ERROR` | Pydantic validation failed |
| `400 Bad Request` | `INVALID_AUTH_CODE` | Auth code malformed (not 8 chars) |
| `401 Unauthorized` | `INVALID_TOKEN` | JWT missing, malformed, or expired |
| `401 Unauthorized` | `INVALID_CREDENTIALS` | Wrong email or password |
| `401 Unauthorized` | `TOKEN_ALREADY_USED` | Refresh token replay detected |
| `402 Payment Required` | `SUBSCRIPTION_INACTIVE` | Plan is not active (payment failed) |
| `404 Not Found` | `NOT_FOUND` | Resource does not exist |
| `409 Conflict` | `EMAIL_EXISTS` | Registration with an existing email |
| `422 Unprocessable Entity` | `VALIDATION_ERROR` | Pydantic field-level validation error |
| `429 Too Many Requests` | `RATE_LIMIT_EXCEEDED` | Monthly or burst limit hit |
| `500 Internal Server Error` | `INTERNAL_ERROR` | Unhandled exception |
| `503 Service Unavailable` | `LLM_UNAVAILABLE` | All LLM providers down, no cached fallback |

### 13.3 FastAPI Exception Handlers

```python
# app/core/exceptions.py
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from jose import JWTError
import uuid
from datetime import datetime, timezone

class IQinsytException(Exception):
    def __init__(self, status_code: int, error: str, message: str):
        self.status_code = status_code
        self.error = error
        self.message = message

def make_error_body(error: str, message: str, request_id: str) -> dict:
    return {
        "error": error,
        "message": message,
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

def register_exception_handlers(app):
    @app.exception_handler(IQinsytException)
    async def iqinsyt_exception_handler(request: Request, exc: IQinsytException):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        return JSONResponse(
            status_code=exc.status_code,
            content=make_error_body(exc.error, exc.message, request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        return JSONResponse(
            status_code=422,
            content=make_error_body(
                "VALIDATION_ERROR",
                f"Validation failed: {exc.errors()[0]['msg']}",
                request_id,
            ),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        # Log the full traceback here (structured logging)
        return JSONResponse(
            status_code=500,
            content=make_error_body("INTERNAL_ERROR", "An unexpected error occurred.", request_id),
        )
```

### 13.4 Request ID Middleware

Every request receives a `X-Request-ID` header (UUID) injected by middleware. This ties logs, error responses, and database records together for debugging.

```python
# app/main.py
from starlette.middleware.base import BaseHTTPMiddleware
import uuid

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

---

## 14. Environment Variables

All configuration is managed via Pydantic `Settings` reading from a `.env` file.

```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    APP_ENV: str = "development"    # "development" | "production"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"

    # PostgreSQL
    DATABASE_URL: str               # asyncpg: "postgresql+asyncpg://user:pass@host:5432/iqinsyt"

    # Redis
    REDIS_URL: str                  # "redis://localhost:6379/0"

    # JWT (RS256)
    JWT_PRIVATE_KEY: str            # Full PEM string (newlines as \n)
    JWT_PUBLIC_KEY: str             # Full PEM string (newlines as \n)

    # OpenAI
    OPENAI_API_KEY: str

    # Pinecone
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str = "iqinsyt-insights"

    # Brave Search
    BRAVE_API_KEY: str

    # Firecrawl
    FIRECRAWL_API_KEY: str

    # Stripe
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str      # From Stripe Dashboard → Webhooks → Signing secret
    STRIPE_STARTER_PRICE_ID: str    # Stripe Price ID for the Starter plan
    STRIPE_PRO_PRICE_ID: str        # Stripe Price ID for the Pro plan

    # CORS
    CORS_ORIGINS: list[str] = ["https://iqinsyt.com", "chrome-extension://"]

settings = Settings()
```

**`.env.example`:**

```bash
# Application
APP_ENV=development
APP_VERSION=1.0.0
LOG_LEVEL=INFO

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://iqinsyt:password@localhost:5432/iqinsyt

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT (RS256) — generate with: python scripts/generate_keypair.py
JWT_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"

# OpenAI
OPENAI_API_KEY=sk-...

# Pinecone
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=iqinsyt-insights

# Brave Search
BRAVE_API_KEY=...

# Firecrawl
FIRECRAWL_API_KEY=...

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_STARTER_PRICE_ID=price_...
STRIPE_PRO_PRICE_ID=price_...

# CORS
CORS_ORIGINS=["http://localhost:5173","https://iqinsyt.com"]
```

**Generating the RS256 key pair:**

```bash
python scripts/generate_keypair.py
# Copy the output values into your .env file
```

On Railway/Render, set `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` as environment variable values with literal newlines (most deployment platforms support this via their dashboard). Alternatively, Base64-encode the PEM strings and decode in `config.py`.

---

## 15. Build & Development Setup

### 15.1 Dependencies (`pyproject.toml`)

```toml
[project]
name = "iqinsyt-backend"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    # Web framework
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "gunicorn>=22.0.0",

    # Pydantic
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",

    # Database
    "sqlalchemy>=2.0.30",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",

    # Redis
    "redis[hiredis]>=5.0.0",

    # Auth
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",

    # OpenAI
    "openai>=1.35.0",

    # Pinecone
    "pinecone-client>=3.2.0",

    # HTTP client
    "httpx>=0.27.0",

    # Firecrawl
    "firecrawl-py>=1.0.0",

    # Stripe
    "stripe>=10.0.0",

    # Utilities
    "python-multipart>=0.0.9",   # for form data
    "cryptography>=42.0.0",      # for key generation
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",             # async test client
    "fakeredis[aioredis]>=2.23.0",
    "factory-boy>=3.3.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]
```

### 15.2 Alembic Setup and Migration Commands

```bash
# Initialise Alembic (run once)
alembic init migrations

# Edit migrations/env.py to use async engine
# (See below for the async env.py template)

# Generate a new migration from model changes
alembic revision --autogenerate -m "initial_schema"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current migration version
alembic current

# Show migration history
alembic history
```

**`migrations/env.py` (async pattern):**

```python
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context
from app.models.base import Base
from app.core.config import settings
import asyncio

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=settings.DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

### 15.3 Local Development

```bash
# Clone and install
git clone <repo>
cd iqinsyt-backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Copy and populate env
cp .env.example .env
# Edit .env with your API keys and local DB/Redis URLs

# Generate RS256 key pair
python scripts/generate_keypair.py   # paste output into .env

# Start local PostgreSQL + Redis (see docker-compose.yml below)
docker-compose up -d db redis

# Run database migrations
alembic upgrade head

# Create Pinecone index (run once)
python scripts/setup_pinecone.py

# Start the API server with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# API is now available at: http://localhost:8000
# Interactive docs: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

### 15.4 Application Entry Point (`app/main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.routers import auth, insight, user, billing
from app.db.session import engine
from app.models.base import Base
import redis.asyncio as aioredis

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    yield
    # Shutdown
    await app.state.redis.aclose()

app = FastAPI(
    title="IQinsyt API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV == "development" else None,
    redoc_url="/redoc" if settings.APP_ENV == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router, prefix="/v1")
app.include_router(insight.router, prefix="/v1")
app.include_router(user.router, prefix="/v1")
app.include_router(billing.router, prefix="/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
```

---

## 16. Deployment

### 16.1 Multi-Stage Dockerfile

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini .

# Non-root user for security
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Gunicorn with uvicorn workers for production
CMD ["gunicorn", "app.main:app", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "30", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

### 16.2 `docker-compose.yml` for Local Development

```yaml
version: "3.9"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./app:/app/app        # hot reload via uvicorn --reload in dev
    command: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: iqinsyt
      POSTGRES_USER: iqinsyt
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U iqinsyt"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

### 16.3 Railway Configuration

Railway auto-detects the `Dockerfile`. Set the following in Railway's environment variables dashboard:

- All variables from `.env.example` (with production values)
- `PORT=8000` — Railway injects `PORT` automatically; ensure Gunicorn binds to it

`railway.toml` (optional, for explicit control):

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "alembic upgrade head && gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 30"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

The `startCommand` runs Alembic migrations before starting Gunicorn on every deploy. This is safe because Alembic is idempotent — it only applies unapplied migrations.

### 16.4 Render Configuration

`render.yaml`:

```yaml
services:
  - type: web
    name: iqinsyt-api
    runtime: docker
    dockerfilePath: ./Dockerfile
    plan: starter          # upgrade to standard for production load
    healthCheckPath: /health
    envVars:
      - key: APP_ENV
        value: production
      - key: DATABASE_URL
        fromDatabase:
          name: iqinsyt-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: iqinsyt-redis
          property: connectionString
      # Add all other secrets via Render dashboard (not in render.yaml)

databases:
  - name: iqinsyt-db
    plan: starter
    databaseName: iqinsyt
    user: iqinsyt

  - name: iqinsyt-redis
    plan: starter
    ipAllowList: []
```

Run migrations on deploy: in Render, add a **Pre-deploy Command**: `alembic upgrade head`.

### 16.5 Health Check Endpoint

The `GET /health` endpoint (Section 4.5) must respond within 5 seconds. Railway and Render probe this URL to determine if the instance is healthy. In production, also check DB and Redis connectivity:

```python
@app.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    db_status = "ok"
    redis_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    try:
        await redis.ping()
    except Exception:
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return {
        "status": overall,
        "db": db_status,
        "redis": redis_status,
        "version": settings.APP_VERSION,
    }
```

---

## 17. Testing Strategy

### 17.1 Test Setup

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run only a specific module
pytest tests/test_compliance.py -v

# Run async tests
pytest --asyncio-mode=auto
```

**`tests/conftest.py`:**

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fakeredis.aioredis import FakeRedis
from app.main import app
from app.models.base import Base
from app.db.session import get_db
from app.core.dependencies import get_redis

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def redis_client():
    return FakeRedis()

@pytest_asyncio.fixture(scope="function")
async def client(db_session, redis_client):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

### 17.2 Auth Tests (`tests/test_auth.py`)

```python
import pytest

@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post("/v1/auth/register", json={
        "email": "test@example.com",
        "password": "securepassword123",
        "full_name": "Test User",
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "securepassword123", "full_name": "A"}
    await client.post("/v1/auth/register", json=payload)
    response = await client.post("/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["error"] == "EMAIL_EXISTS"

@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/v1/auth/register", json={
        "email": "user@example.com", "password": "correctpassword", "full_name": "X"
    })
    response = await client.post("/v1/auth/login", json={
        "email": "user@example.com", "password": "wrongpassword"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_refresh_token_replay_attack(client):
    """After using a refresh token, re-using it should return 401 and revoke all tokens."""
    reg = await client.post("/v1/auth/register", json={
        "email": "replay@example.com", "password": "securepassword123", "full_name": "R"
    })
    refresh_token = reg.json()["refresh_token"]

    # First refresh — succeeds
    r1 = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r1.status_code == 200

    # Replay the original token — must fail
    r2 = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r2.status_code == 401
    assert r2.json()["error"] == "TOKEN_ALREADY_USED"
```

### 17.3 Compliance Tests (`tests/test_compliance.py`)

Test cases must cover every pattern category. Include both positive (should trigger) and negative (should pass) cases.

```python
import pytest
from app.services.compliance_service import scan_section, scan_sections

# --- SHOULD FAIL (triggers pattern) ---
@pytest.mark.parametrize("text", [
    "Team A is likely to win based on current form.",
    "The odds favour the home side this weekend.",
    "This is projected to be a dominant performance.",
    "You should consider backing the away team.",
    "Team B has the edge going into the match.",
    "Their star player is guaranteed to shine.",
    "Their record makes them the clear favourite.",
    "There is a 75% chance of a home win.",
    "They are bound to struggle in wet conditions.",
])
def test_compliance_violations(text):
    triggers = scan_section(text)
    assert len(triggers) > 0, f"Expected violation but none found in: {text!r}"

# --- SHOULD PASS (neutral language) ---
@pytest.mark.parametrize("text", [
    "Team A has won 3 of their last 5 home fixtures.",
    "The last encounter between these teams ended 2-1.",
    "Both teams have injury concerns entering this match.",
    "Recent data on player fitness is limited.",
    "Weather conditions may be a factor in this outdoor event.",
    "This event has historically seen high scoring.",
    "Data from the last 12 months shows variable performance.",
])
def test_compliance_pass(text):
    triggers = scan_section(text)
    assert triggers == [], f"Expected no violations but found {triggers!r} in: {text!r}"

def test_scan_sections_identifies_per_section_violations():
    sections = {
        "eventSummary": "This is a neutral summary of the event.",
        "keyVariables": "Team A is likely to win due to home advantage.",
        "historicalContext": "Historical records show 5 matches played.",
    }
    result = scan_sections(sections)
    assert result["eventSummary"] == []
    assert len(result["keyVariables"]) > 0
    assert result["historicalContext"] == []
```

### 17.4 AI Pipeline Mocking (`tests/test_insight.py`)

The OpenAI, Brave Search, and Firecrawl clients are mocked to avoid live API calls and achieve fast, deterministic tests.

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

MOCK_LLM_RESPONSE = {
    "eventSummary": "Arsenal and Chelsea will meet in the Premier League.",
    "keyVariables": "Recent form, injury record, and pitch conditions.",
    "historicalContext": "These teams have met 200 times. Arsenal lead the series.",
    "currentDrivers": "Arsenal are unbeaten in their last 6 matches.",
    "riskFactors": "Chelsea have three key players unavailable.",
    "dataConfidence": "Data sourced from official Premier League records.",
    "dataGaps": "Training session reports from this week are not public.",
}

@pytest.mark.asyncio
async def test_insight_cache_hit(client, redis_client):
    """Cache hit should return without calling the LLM."""
    import json
    from app.services.cache_service import make_cache_key, CACHE_TTL_SECONDS

    cached_payload = {
        "requestId": "abc123",
        "cached": True,
        "cachedAt": "2026-04-02T10:00:00Z",
        "sections": MOCK_LLM_RESPONSE,
        "dataRetrievalAvailable": True,
        "generatedAt": "2026-04-02T10:00:00Z",
    }
    key = make_cache_key("Arsenal vs Chelsea")
    await redis_client.setex(key, CACHE_TTL_SECONDS, json.dumps(cached_payload))

    # Register user and get token
    reg = await client.post("/v1/auth/register", json={
        "email": "cache@test.com", "password": "pass12345", "full_name": "T"
    })
    token = reg.json()["access_token"]

    with patch("app.services.llm_service.call_llm") as mock_llm:
        response = await client.post(
            "/v1/insight",
            json={"eventTitle": "Arsenal vs Chelsea", "eventSource": "bbc.co.uk", "timestamp": 1000},
            headers={"Authorization": f"Bearer {token}"},
        )
        mock_llm.assert_not_called()

    assert response.status_code == 200
    assert response.json()["cached"] is True

@pytest.mark.asyncio
async def test_insight_full_pipeline(client):
    """Full pipeline run when no cache exists."""
    reg = await client.post("/v1/auth/register", json={
        "email": "pipeline@test.com", "password": "pass12345", "full_name": "P"
    })
    token = reg.json()["access_token"]

    with (
        patch("app.services.search_service.gather_search_results", new_callable=AsyncMock, return_value=[]),
        patch("app.services.scrape_service.scrape_urls", new_callable=AsyncMock, return_value=("", False)),
        patch("app.services.llm_service.call_llm", new_callable=AsyncMock, return_value=MOCK_LLM_RESPONSE),
        patch("app.services.vector_service.semantic_match", new_callable=AsyncMock, return_value=None),
        patch("app.services.vector_service.get_embedding", new_callable=AsyncMock, return_value=[0.0] * 1536),
        patch("app.services.insight_service.pinecone_index") as mock_pine,
    ):
        mock_pine.upsert = MagicMock()
        response = await client.post(
            "/v1/insight",
            json={"eventTitle": "Liverpool vs Everton", "eventSource": "skysports.com", "timestamp": 1000},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["cached"] is False
    assert data["sections"]["eventSummary"] == MOCK_LLM_RESPONSE["eventSummary"]
    assert data["dataRetrievalAvailable"] is False
```

### 17.5 Rate Limit Tests (`tests/test_rate_limit.py`)

```python
@pytest.mark.asyncio
async def test_monthly_limit_enforced(client, redis_client):
    """Free plan users should be blocked after 10 queries."""
    reg = await client.post("/v1/auth/register", json={
        "email": "limit@test.com", "password": "pass12345", "full_name": "L"
    })
    token = reg.json()["access_token"]
    user_id = ...  # extract from JWT

    # Manually set the counter to the limit
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    key = f"rate:{user_id}:{now.strftime('%Y-%m')}"
    await redis_client.set(key, 10)

    with patch("app.services.llm_service.call_llm", new_callable=AsyncMock, return_value=MOCK_LLM_RESPONSE):
        response = await client.post(
            "/v1/insight",
            json={"eventTitle": "Test Event", "eventSource": "test.com", "timestamp": 1000},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 429
    assert response.json()["error"] == "RATE_LIMIT_EXCEEDED"
```

### 17.6 k6 Load Test Targets

Use [k6](https://k6.io/) for load testing the production deployment.

**Target metrics:**

| Endpoint | Target P95 Latency | Target RPS |
|---|---|---|
| `GET /health` | < 50ms | 100 |
| `POST /v1/auth/login` | < 200ms | 20 |
| `POST /v1/insight` (cache hit) | < 300ms | 50 |
| `POST /v1/insight` (full pipeline) | < 6000ms | 5 |

**`k6_load_test.js` (basic smoke test):**

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    stages: [
        { duration: '30s', target: 10 },   // ramp up to 10 users
        { duration: '1m',  target: 10 },   // hold
        { duration: '15s', target: 0 },    // ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<6000'],
        http_req_failed:   ['rate<0.01'],
    },
};

const BASE_URL = __ENV.BASE_URL || 'https://api.iqinsyt.com';

export default function () {
    // Health check
    const health = http.get(`${BASE_URL}/health`);
    check(health, { 'health ok': (r) => r.status === 200 });

    // Insight request (requires a valid token in TEST_TOKEN env var)
    const token = __ENV.TEST_TOKEN;
    const insight = http.post(
        `${BASE_URL}/v1/insight`,
        JSON.stringify({ eventTitle: 'Arsenal vs Chelsea', eventSource: 'test.com', timestamp: Date.now() }),
        { headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` } },
    );
    check(insight, {
        'insight 200': (r) => r.status === 200,
        'insight has sections': (r) => r.json().sections !== undefined,
    });

    sleep(1);
}
```

Run: `k6 run -e BASE_URL=https://api.iqinsyt.com -e TEST_TOKEN=<token> k6_load_test.js`

---

*This document covers the IQinsyt backend API in full. The Chrome extension is documented in `architecture.md`. The web app frontend is documented separately.*

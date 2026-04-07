# IQinsyt Chrome Extension — Full Architecture & Developer Guide

> **Scope:** This document covers the Chrome extension only — its structure, frontend, backend integration, AI pipeline, data flow, and everything a developer needs to build it from scratch. The web app is a separate deliverable.
>
> **Current backend alignment:** this repository currently exposes `POST /v1/research` and `GET /health` with API-key auth (`X-API-Key`) from `src/api/server.py`. JWT-based extension login endpoints are planned and tracked in `architecture_backend.md`.

---

## Table of Contents

1. [What Is This Extension?](#1-what-is-this-extension)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Extension Project Structure](#3-extension-project-structure)
4. [Manifest V3 Setup](#4-manifest-v3-setup)
5. [Frontend — Side Panel UI](#5-frontend--side-panel-ui)
6. [Event Detection Engine](#6-event-detection-engine)
7. [Backend Integration](#7-backend-integration)
8. [AI Pipeline — How the AI Works](#8-ai-pipeline--how-the-ai-works)
9. [Neutrality & Compliance Layer](#9-neutrality--compliance-layer)
10. [End-to-End Data Flow (Step by Step)](#10-end-to-end-data-flow-step-by-step)
11. [Error Handling & Fallbacks](#11-error-handling--fallbacks)
12. [Authentication & Security](#12-authentication--security)
13. [State Management](#13-state-management)
14. [Build & Development Setup](#14-build--development-setup)
15. [Loading the Extension in Chrome](#15-loading-the-extension-in-chrome)
16. [Testing Strategy](#16-testing-strategy)

---

## 1. What Is This Extension?

IQinsyt is a **neutral AI-powered research utility** delivered as a Chrome extension (Manifest V3). It sits alongside any sports or prediction-market page (Kalshi, Polymarket, Sportsbet, Bet365, TAB, etc.), detects the event the user is viewing, and returns structured, factual research output in 2–5 seconds.

**What it is NOT:**
- Not a betting tool
- Does not show odds, predictions, or recommendations
- Does not integrate with platform APIs or read cookies/session data from host pages
- Does not modify host page content or data — only injects a temporary highlight overlay and toast UI during picker mode

**What it IS:**
- A research assistant that surfaces factual context about an event
- Platform-agnostic — works on any page via DOM parsing
- Delivers a structured 7-section research output every time

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CHROME BROWSER                           │
│                                                                 │
│   Host Page (Kalshi, Polymarket, etc.)                            │
│        │                                                        │
│        │  Kalshi auto-detect (SPA route observer)               │
│        │  Interactive element picker (user-triggered)            │
│        │  PING_CONTENT_SCRIPT (site auth check)                  │
│        ▼                                                        │
│   Content Script  ──────────────────────►  Side Panel UI       │
│   (detection + parsing)    Chrome messaging  (React/TypeScript)  │
│                                                  │              │
│   Background Service Worker                      │              │
│   (manages auth, coordinates messaging,          │              │
│    monitors tab changes, broadcasts site auth)   │              │
└──────────────────────────────────────────────────┼─────────────┘
                                                   │
                                          HTTPS + API key
                                                   │
                                                   ▼
                                        ┌──────────────────┐
                                        │  FastAPI Backend  │
                                        │ (API key auth)    │
                                        └────────┬─────────┘
                                                 │
                                                 ▼
                                        ┌──────────────────┐
                                        │  Backend Insight  │
                                        │     Engine        │
                                        │ (Python/FastAPI)  │
                                        └────────┬─────────┘
                                                 │
                              ┌──────────────────┼──────────────────┐
                              │                  │                  │
                              ▼                  ▼                  ▼
                        MongoDB TTL      Redis / Vector      PostgreSQL
                          (current)       (planned)          (planned)
                              │
                              ▼
                     Brave Search API
                     Firecrawl (planned)
                              │
                              ▼
                        LLM API Call
                     (GPT-4o-mini current)
                              │
                              ▼
                  Neutrality & Compliance Layer
                     (mandatory filter pass)
                              │
                              ▼
                   Structured 7-Section Response
                       → Back to Extension
```

---

## 3. Extension Project Structure

```
iqinsyt-extension/
├── public/
│   ├── favicon.svg              # Browser/extension icon asset
│   └── icons.svg                # Additional static icon asset bundle
│
├── src/
│   ├── background/
│   │   └── index.ts             # Background service worker — message router + API bridge
│   │
│   ├── content/
│   │   ├── content-script.ts    # Content script entrypoint — auto-detect on Kalshi + picker + PING handler
│   │   ├── picker.ts            # Interactive element picker (hover highlight → click → parse)
│   │   └── sites/
│   │       └── kalshi/
│   │           ├── autoDetect.ts       # Auto-detect market on Kalshi detail pages
│   │           └── parseMarket.ts      # Parse Kalshi listing tiles and detail pages
│   │
│   ├── sidepanel/
│   │   ├── main.tsx             # React bootstrap entrypoint
│   │   ├── App.tsx              # Reducer + provider root — phase-based UI composition
│   │   ├── context.tsx          # AppContext and useAppContext helper
│   │   └── index.html           # Side panel HTML shell
│   │
│   ├── api/
│   │   ├── client.ts            # API runtime client + typed fetch errors
│   │   └── types.ts             # API request/response contracts
│   │
│   ├── auth/
│   │   └── tokenManager.ts      # Chrome storage token handling + auto-refresh
│   │
│   ├── components/
│   │   ├── StatusBar.tsx        # Top status indicator reflecting current phase
│   │   ├── EventCard.tsx        # Detected event summary + analyse action
│   │   ├── ManualInput.tsx      # Manual event input form (fallback when detection fails)
│   │   ├── SectionBlock.tsx     # Expandable/collapsible research section block
│   │   ├── ResearchOutput.tsx   # 7-section research output rendering + meta badges
│   │   └── ErrorState.tsx       # Error state UI block with dismiss action
│   │
│   ├── hooks/
│   │   ├── useAuth.ts           # Auth/session hook — token check + plan sync
│   │   ├── useEventDetection.ts # Message listener for detected events
│   │   └── useInsightQuery.ts   # Analysis request/response hook
│   │
│   ├── shared/
│   │   └── types.ts             # Shared app/message/state/event contracts
│   │
│   └── index.css                # Global design tokens + component styling
│
├── .env                         # VITE_BACKEND_URL=http://localhost:8080
├── manifest.json                # Manifest V3 contract (at project root)
├── package.json                 # Scripts and dependencies
├── pnpm-lock.yaml               # pnpm lockfile
├── vite.config.ts               # Vite + CRX build config
└── tsconfig.json                # Root TypeScript config
```

---

## 4. Manifest V3 Setup

`manifest.json` at project root — every field below is required:

```json
{
  "manifest_version": 3,
  "name": "IQinsyt",
  "version": "1.0.0",
  "description": "Neutral AI-powered research for sports and prediction events.",

  "permissions": [
    "sidePanel",
    "storage",
    "activeTab",
    "scripting"
  ],

  "host_permissions": [
    "https://*.polymarket.com/*",
    "https://*.kalshi.com/*",
    "https://*.metaculus.com/*",
    "https://*.manifold.markets/*",
    "https://*.predictit.org/*",
    "https://*.betfair.com/*",
    "https://*.smarkets.com/*"
  ],

  "background": {
    "service_worker": "src/background/index.ts",
    "type": "module"
  },

  "content_scripts": [
    {
      "matches": [
        "https://*.polymarket.com/*",
        "https://*.kalshi.com/*",
        "https://*.metaculus.com/*",
        "https://*.manifold.markets/*",
        "https://*.predictit.org/*",
        "https://*.betfair.com/*",
        "https://*.smarkets.com/*"
      ],
      "js": ["src/content/content-script.ts"],
      "run_at": "document_idle"
    }
  ],

  "side_panel": {
    "default_path": "src/sidepanel/index.html"
  },

  "action": {
    "default_title": "Open IQinsyt"
  }
}
```

**Key notes for the developer:**
- `sidePanel` permission is required for the side panel API (Chrome 114+)
- `host_permissions` lists specific prediction market domains — the content script only runs on these sites
- `scripting` permission is used to inject the content script into the active tab when the picker is activated
- No `popup` is defined — the extension opens a side panel, never a popup
- The background script is a **service worker** (MV3 requirement) — it cannot use `localStorage`, only `chrome.storage`
- Entry points use `.ts` source paths; `@crxjs/vite-plugin` compiles them to `.js` in `dist/`
- No `icons` block is defined yet — Chrome uses a default icon until icon assets are added

---

## 5. Frontend — Side Panel UI

### Technology
- **React 19** + **TypeScript**
- **Vite** + **@crxjs/vite-plugin** for extension bundling
- **Babel** with **React Compiler** (`babel-plugin-react-compiler`) for automatic memoization
- Plain CSS custom properties in `src/index.css` — no CSS Modules, no Tailwind, no UI component library

### Side Panel Entry Point

`src/sidepanel/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>IQinsyt</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="main.tsx"></script>
  </body>
</html>
```

### App Shell (`App.tsx`)

The app has seven states:

```
App
 ├── [idle]              → "Pick element" button
 ├── [picking]           → Instructions: "Click a market card"
 ├── [manual]            → ManualInput + "Pick element instead" button
 ├── [detected]          → EventCard + "Analyse" button
 ├── [loading]           → Spinner + "Analysing event data..."
 ├── [result]            → EventCard + ResearchOutput (7 sections)
 └── [error]             → ErrorState with dismiss action
```

```tsx
// src/sidepanel/App.tsx
type AppPhase = 'idle' | 'picking' | 'detected' | 'loading' | 'result' | 'error' | 'manual';
```

### Component Breakdown

| Component | Purpose |
|---|---|
| `EventCard` | Displays the detected event name and source page |
| `ManualInput` | Text input form — shown when auto-detect fails |
| `StatusBar` | Phase-based status: "Ready to analyse", "Picking element", "Event detected", "Analysing...", "Done", "Error" |
| `ResearchOutput` | Renders all 7 research sections |
| `SectionBlock` | Renders a single section (title + body) |
| `ErrorState` | Displays error messages for each failure type |

### Design Rules (Non-negotiable)

- **No green or red colours anywhere in the UI** — use neutral greys, whites, and blues only
- **No directional arrows** (up/down) — never imply an outcome direction
- **No percentage chances, odds, or probability language** in the UI layer
- Side panel width: fixed at Chrome's default side panel width (~400px)
- Font: system font stack — `font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`

### The 7 Output Sections

Every research result renders exactly these 7 sections in order:

```
1. Event Summary
2. Key Variables
3. Historical Context
4. Current Drivers
5. Risk Factors
6. Data Confidence / Reliability
7. Data Gaps / Unknowns
```

Each section renders as a collapsible `SectionBlock` with a title and plain-text body. If a section is missing (partial output), render it with label `"[Data unavailable for this section]"` — never skip it silently.

---

## 6. Event Detection Engine

### How Detection Works

The content script runs on configured host pages (Polymarket, Kalshi, Metaculus, etc.). It uses two mechanisms:

**Mode 1 — Kalshi Auto-Detect (passive, automatic)**

On `kalshi.com` detail pages, the content script auto-detects the market without user interaction:

```typescript
// src/content/content-script.ts

// Runs on initial load and on SPA navigation
function tryAutoDetect(): void {
  const market = detectKalshiDetailPage();
  if (market) {
    chrome.runtime.sendMessage({ type: 'MARKETS_DETECTED', payload: [market] });
  }
}

if (window.location.hostname === 'kalshi.com') {
  setTimeout(tryAutoDetect, 1500);
  // Also re-detect on SPA route changes
  new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      setTimeout(tryAutoDetect, 1000);
    }
  }).observe(document, { subtree: true, childList: true });
}
```

The `detectKalshiDetailPage()` function in `parseElementText.ts` looks for:
- An `<h1>` element with the market title (min 5 chars)
- Outcome rows with percentage headers (`h2.typ-headline-x10` containing `\d+%`)
- Volume information from `[class*="typ-body-x20"]` elements

**Mode 2 — Interactive Element Picker (user-triggered)**

When auto-detect is not available (non-Kalshi pages, or Kalshi listing pages), the user clicks "Pick element" in the side panel:

```typescript
// src/content/picker.ts

export function activatePicker(): void {
  // Inject highlight styles
  // Add mouseover/mouseout/click/keydown listeners
  // Show toast: "Select a betting market on the page"
}
```

The picker workflow:
1. Side panel dispatches `START_PICKING` → background → content script
2. Content script calls `activatePicker()` — adds `mouseover`, `click`, `keydown` listeners
3. On `mouseover`: walks up DOM tree to find market container, highlights with purple outline (`#aa3bff`)
4. On `click`: parses the selected element via `parseElementText()`, sends `MARKETS_DETECTED` with payload
5. On `Escape`: deactivates picker, sends `PICKER_CANCELLED`

The picker includes a debug mode (`Ctrl+Shift+D`) that logs parsing details to console.

**Element Parsing (site-specific parsers)**

The parser in `src/content/sites/kalshi/parseMarket.ts` tries two strategies:

1. **Kalshi listing tile parser** — looks for `[data-testid="market-tile"]` elements, extracts title from `<h2>`, outcomes from `[aria-valuenow]` progress bars, volume from text matching `\$[\d,]+[kmb]?`
2. **Kalshi detail page parser** — looks for `h2.typ-headline-x10` percentage headers and `span.typ-body-x30` outcome labels within the outcomes container

Each parsed element produces a `DetectedMarket`:

```typescript
interface DetectedMarket {
  id: string;              // slugified title, max 64 chars
  title: string;           // e.g. "Will Bitcoin reach $100k by 2025?"
  source: string;          // hostname, e.g. "kalshi.com"
  url: string | null;      // current page URL
  outcomes: DetectedOutcome[];  // [{ label: "Yes", probability: "65%" }, ...]
  volume: string | null;   // e.g. "$1.2M"
}
```

**Fallback Chain**

```
Kalshi auto-detect (URL-based, on detail pages)
    ↓ not on Kalshi or no market found
User clicks "Pick element" → interactive picker
    ↓ picker click parses element
Parse succeeds → MARKETS_DETECTED
    ↓ parse fails
DETECTION_FAILED → ManualInput shown in side panel
    ↓ user types manually
Manual submit → EVENT_DETECTED with source: 'manual'
```

### Chrome Messaging Flow

```
Content Script  ──sendMessage──►  Background Service Worker
                                          │
                               relay or handle
                                          │
                                          ▼
                                     Side Panel (React)
                               listens via chrome.runtime.onMessage
```

Message types (defined in `src/shared/types.ts`):

```typescript
type MessageType =
  | 'MARKETS_DETECTED'      // content script → background → side panel (auto or picker)
  | 'EVENT_DETECTED'        // content script → background → side panel (legacy/generic)
  | 'REQUEST_ANALYSIS'      // side panel → background → API
  | 'ANALYSIS_RESULT'       // background → side panel
  | 'ANALYSIS_ERROR'        // background → side panel (API call failed)
  | 'DETECTION_FAILED'      // background → side panel (trigger manual input)
  | 'AUTH_REQUIRED'         // background → side panel
  | 'START_PICKER'          // side panel → background → content script
  | 'PICKER_CANCELLED';     // content script → background → side panel

interface ExtensionMessage {
  type: MessageType;
  payload?: unknown;
}
```

---

## 7. Backend Integration

### API Client (`src/api/client.ts`)

The extension communicates with the backend over HTTPS only. Uses `fetch` (available in MV3 service workers).

```typescript
const BASE_URL = import.meta.env.VITE_BACKEND_URL; // e.g. http://localhost:8000
const API_KEY = import.meta.env.VITE_BACKEND_API_KEY;

async function authedFetch(path: string, init: RequestInit): Promise<Response> {
  if (!API_KEY) throw new AuthError('Missing API key');

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
      ...init.headers,
    },
  });

  if (response.status === 401) throw new AuthError('Invalid API key');
  if (!response.ok) throw new ApiError(`Request failed: ${response.status}`);

  return response;
}
```

Input sanitization happens inline before sending:

```typescript
function sanitize(text: string): string {
  return text.replace(/<[^>]*>/g, '').trim().slice(0, 500);
}
```

### Backend Endpoints Used by Extension

| Endpoint | Method | Purpose |
|---|---|---|
| `/v1/research` | POST | Submit event, get 7-section research |
| `/health` | GET | Service + DB health check |

Planned (not currently implemented in this backend repository): `/v1/auth/token`, `/v1/auth/refresh`, `/v1/user/plan`.

### Request Payload

```typescript
interface ResearchRequest {
  eventTitle: string;     // e.g. "Manchester City vs Arsenal"
  eventSource: string;    // hostname, e.g. "sportsbet.com.au"
  timestamp: number;      // Unix ms
}
```

### Response Structure

```typescript
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  request_id: string;
  timestamp: string;
}

interface ResearchResponse {
  cached: boolean;
  cachedAt: string | null;
  sections: {
    eventSummary: string;
    keyVariables: string;
    historicalContext: string;
    currentDrivers: string;
    riskFactors: string;
    dataConfidence: string;
    dataGaps: string;
  };
  dataRetrievalAvailable: boolean;
  generatedAt: string;
}
```

---

## 8. AI Pipeline — How the AI Works

This section describes what happens inside the backend when the extension sends a request. The developer building the extension does not implement this, but must understand it to handle responses correctly.

### Step-by-Step AI Pipeline

```
Extension POST /v1/research
         │
         ▼
1. API key validated by FastAPI dependency
         │
         ▼
2. MongoDB cache lookup
   → Cache HIT:  return immediately (response tagged "Cached [Date]")
   → Cache MISS: continue
         │
         ▼
3. Public data retrieval
   ├── Brave Search API  (avg 2.5 queries/session)
   │     Searches: "[event] news", "[event] analysis", "[event] preview"
   └── (No Firecrawl in current implementation)
         │
         ▼
4. Prompt Assembly
   System prompt:    "You are a neutral research analyst..."
   Event context:    Injected event title + source page
   Research context: Scraped/searched content (if available)
   Output structure: Enforced 7-section format
   Negative constraints: Explicit prohibitions (see Section 9)
         │
         ▼
5. LLM API Call
   Default model: GPT-4o-mini
   Hard timeout:   8 seconds
   → Timeout: return partial output with missing section labels
         │
         ▼
6. Neutrality & Compliance Layer
   → PASS: cache result in MongoDB (TTL 4h), return to extension
   → FAIL: re-queue for LLM regeneration (max 3 attempts)
   → Still failing after retries: quarantine non-compliant sections
         │
         ▼
7. Structured JSON response → extension
```

### LLM Prompt Structure (Overview)

```
[SYSTEM]
You are a neutral research analyst. Your role is to surface factual,
structured information about the following event. You must not make
predictions, issue recommendations, suggest probabilities, or use
persuasive language of any kind.

[EVENT CONTEXT]
Event: {eventTitle}
Detected on: {eventSource}

[RESEARCH CONTEXT]
{scrapedContent}

[OUTPUT INSTRUCTIONS]
Return exactly these 7 sections:
1. Event Summary
2. Key Variables
3. Historical Context
4. Current Drivers
5. Risk Factors
6. Data Confidence / Reliability
7. Data Gaps / Unknowns

[NEGATIVE CONSTRAINTS]
Do NOT use: "likely", "expected", "odds favour", "recommend",
"consider backing", or any language that ranks or predicts outcomes.
```

### LLM Provider Failover

```
GPT-4o-mini (primary)
    ↓ provider outage / timeout
GPT-4o (secondary fallback)
    ↓ also unavailable
Serve most recent cached result (labelled with cache date)
    ↓ no cache exists
Return error: "Insight temporarily unavailable"
```

---

## 9. Neutrality & Compliance Layer

This is a **mandatory, non-bypassable** filter that every LLM response passes through before it reaches the extension. The extension developer must understand this layer because:
- Partial outputs are a valid, expected response state
- Every compliance intervention is audit-logged

### Blocked Patterns (Hard Rules)

The compliance layer scans every LLM output for the following and rejects it if found:

```
Predictive language:
  "likely to win", "expected to", "odds favour", "probability of",
  "projected", "anticipated", "forecast"

Recommendation language:
  "recommended bet", "consider backing", "favourable", "good pick",
  "strong case for", "worth backing"

Emotionally charged phrasing:
  "dominant", "unstoppable", "inevitably", "sure to", "guaranteed"

Ranking outcomes by likelihood:
  Any language that implies one outcome is more probable than another
```

### Compliance Flow

```
LLM output received
      │
      ▼
Pattern scan (regex + semantic check)
      │
 PASS │       FAIL │
      │            ▼
      │     Re-queue for LLM regeneration
      │            │
      │      Attempt 2 ──PASS──►  Cache + Return
      │            │
      │           FAIL
      │            │
      │      Attempt 3 ──PASS──►  Cache + Return
      │            │
      │           FAIL
      │            ▼
      │     Return partial output (whatever sections passed)
      │     Log intervention: timestamp + trigger phrase + action
      ▼
Cache result in MongoDB TTL collection
Return to extension
```

### What the Extension Must Handle

- A valid `sections` object may have some fields as empty strings or `"[Unavailable]"` — render them gracefully
- The `cached: true` flag means show "Cached [cachedAt date]" label in the UI
- `dataRetrievalAvailable: false` means show "Data retrieval unavailable" label

---

## 10. End-to-End Data Flow (Step by Step)

This is the complete journey of a single user request:

```
STEP 1 — User opens a supported page
  User navigates to e.g. sportsbet.com.au/match/123
  Chrome loads the page normally. Extension content script is already injected.

STEP 2 — Content script activates
  MutationObserver watches document.body for DOM changes.
  Once the page settles, extractEventFromDOM() runs.
  Detected event: { title: "Arsenal vs Chelsea", source: "sportsbet.com.au" }

STEP 3 — Event sent to background service worker
  chrome.runtime.sendMessage({ type: 'EVENT_DETECTED', payload: event })

STEP 4 — Background worker opens side panel
  chrome.sidePanel.open({ windowId: currentWindow.id })
  Forwards EVENT_DETECTED to side panel.

STEP 5 — Side panel displays detected event
  EventCard renders "Arsenal vs Chelsea (sportsbet.com.au)"
  "Analyse" button appears.
  StatusBar shows: "Event detected"

  [If no event detected → ManualInput shown instead. User types event. Go to Step 5b.]

STEP 6 — User clicks "Analyse"
  Side panel fires REQUEST_ANALYSIS message to background worker.
  StatusBar shows: "Analysing..."

STEP 7 — Background worker calls backend
  POST /v1/research with X-API-Key + event payload

STEP 8 — Backend receives request
  Validates X-API-Key.
  If invalid key → 401 → extension shows "Invalid API key"

STEP 9 — Backend checks MongoDB cache
  Key: hash(eventTitle + date)
  HIT  → return cached response immediately (response time: ~50ms)
  MISS → continue to Step 10

STEP 10 — Public data retrieval
  Brave Search API: queries "[event] news", "[teams] recent form"
  Results assembled into research context string.

STEP 11 — Prompt assembly
  System prompt + event context + research context + output structure + negative constraints
  Total token budget managed to stay within model context limits.

STEP 12 — LLM call
  Model: GPT-4o-mini
  Hard timeout: 8 seconds
  [If timeout → return partial output with available sections]

STEP 13 — Neutrality & Compliance Layer
  Regex + semantic scan of LLM output.
  PASS → cache in MongoDB TTL collection (4 hours), go to Step 14.
  FAIL → re-queue (max 2 more attempts), then return partial output.

STEP 14 — Response returned to extension
  Backend returns API envelope with ResearchResponse payload.
  Background worker receives it, sends ANALYSIS_RESULT to side panel.

STEP 15 — Side panel renders result
  StatusBar: "Done"
  ResearchOutput component renders all 7 SectionBlocks.
  If cached: shows "Cached [date]" label.
  If dataRetrievalAvailable=false: shows "Data retrieval unavailable" label.
  User can copy, save, or re-run.

TOTAL TIME TARGET: 2–5 seconds (cache hit: <200ms)
```

---

## 11. Error Handling & Fallbacks

Every error state must be visible to the user — no silent failures.

| Failure | Extension Behaviour | UI Message |
|---|---|---|
| No event detected | Show ManualInput | "No event detected — enter manually" |
| Auth failure (401) | Block request | "Invalid API key." |
| LLM timeout (>8s) | Return partial output | "Partial result — some sections unavailable" |
| LLM provider outage | Failover → serve cache | Show cached result with date label |
| Compliance rejection (3rd attempt) | Return partial output | "Partial result — compliance filter applied" |
| Network offline | Show error | "No connection. Please check your network." |
| Backend 5xx | Show error + retry button | "Something went wrong. Try again." |

### Error Handling in Code

```typescript
// src/api/client.ts
try {
  const result = await requestInsight(event);
  dispatch({ type: 'ANALYSIS_RESULT', payload: result });
} catch (e) {
  if (e instanceof AuthError) {
    dispatch({ type: 'AUTH_REQUIRED' });
  } else if (e.name === 'TimeoutError') {
    dispatch({ type: 'SHOW_ERROR', message: 'Request timed out. Try again.' });
  } else {
    dispatch({ type: 'SHOW_ERROR', message: 'Something went wrong. Try again.' });
  }
}
```

---

## 12. Authentication & Security

### Current Backend Auth (This Repository)

The current FastAPI backend in this repository uses a shared API key.

```
1. Extension reads VITE_BACKEND_API_KEY from build-time env
2. Every request includes X-API-Key header
3. Backend validates key in FastAPI dependency
4. If invalid/missing key → 401 INVALID_API_KEY
```

### Planned JWT Flow (Future)

```
1. User logs in via web app → receives JWT access token + refresh token
2. Extension stores tokens in chrome.storage.local (NOT localStorage)
3. Every API request includes: Authorization: Bearer <accessToken>
4. When accessToken expires (check exp claim before request):
     → call POST /v1/auth/refresh with refreshToken
     → store new accessToken
5. If refresh fails → clear tokens, show login prompt
```

### Token Storage

```typescript
// src/auth/token.ts

const TOKEN_KEY = 'iqinsyt_auth';

export async function saveTokens(access: string, refresh: string) {
  await chrome.storage.local.set({
    [TOKEN_KEY]: { access, refresh, savedAt: Date.now() }
  });
}

export async function getAccessToken(): Promise<string | null> {
  const data = await chrome.storage.local.get(TOKEN_KEY);
  const tokens = data[TOKEN_KEY];
  if (!tokens) return null;
  // Check if token is about to expire (within 60 seconds)
  const payload = JSON.parse(atob(tokens.access.split('.')[1]));
  if (payload.exp * 1000 - Date.now() < 60_000) {
    return await refreshAccessToken(tokens.refresh);
  }
  return tokens.access;
}
```

### Security Rules

- **Never log API keys or tokens** in console or error messages
- **Never send API keys/tokens in URL query params** — header only
- All backend communication over **HTTPS only** — no HTTP fallback
- Input from the DOM (event title) must be **sanitized** before sending: strip HTML tags, limit to 500 characters
- Content Security Policy in manifest: restrict `script-src` and `connect-src` to known domains

---

## 13. State Management

The side panel is a standalone React app. Use React's built-in `useReducer` + `useContext` for state — no need for Redux at MVP scale.

### App State Shape

```typescript
interface AppState {
  phase: AppPhase;                    // 'idle' | 'picking' | 'detected' | 'loading' | 'result' | 'error' | 'manual'
  detectedEvent: DetectedEvent | null;
  result: InsightResponse | null;
  error: string | null;
  user: UserInfo;                     // { isAuthenticated: boolean; plan: 'free' | 'starter' | 'pro' | null }
}
```

### State Transitions

```
idle ──────────────────────► picking   (user clicks "Pick element")
picking ───────────────────► detected  (MARKETS_DETECTED from picker click)
picking ───────────────────► idle      (PICKER_CANCELLED via Escape key, no prior event)
picking ───────────────────► detected  (PICKER_CANCELLED via Escape key, had prior event)
idle ──────────────────────► manual    (MARKETS_DETECTED with empty payload)
manual ────────────────────► loading   (user submits manual input)
detected ──────────────────► loading   (user clicks Analyse)
loading ────────────────────► result   (ANALYSIS_RESULT received)
loading ────────────────────► error    (ANALYSIS_ERROR or SHOW_ERROR)
result ─────────────────────► loading  (user clicks Re-run)
error ──────────────────────► idle     (user dismisses error)
any ────────────────────────► idle     (AUTH_REQUIRED → reset to initial state)
```

---

## 14. Build & Development Setup

### Prerequisites

```bash
node >= 20.x
pnpm >= 9.x
```

### Initial Setup

```bash
git clone <repo>
cd iqinsyt-extension
pnpm install
```

`.env` file (already present in repo):
```
VITE_BACKEND_URL=http://localhost:8000
VITE_BACKEND_API_KEY=dev-key-change-me
```

### Build Commands

```bash
# Development build (watch mode with HMR)
pnpm dev

# Production build (outputs to /dist)
pnpm build

# Type check
pnpm -s tsc --noEmit

# Lint
pnpm lint
```

### Vite Config for Chrome Extension

Uses `@crxjs/vite-plugin` for the multi-entry-point build and `@rolldown/plugin-babel` with `babel-plugin-react-compiler` for automatic React memoization:

```bash
pnpm add -D @crxjs/vite-plugin @rolldown/plugin-babel babel-plugin-react-compiler
```

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { crx } from '@crxjs/vite-plugin';
import { babel } from '@rolldown/plugin-babel';
import manifest from './manifest.json';

export default defineConfig({
  plugins: [
    react(),
    babel({
      include: ['src/**/*.{js,jsx,ts,tsx}'],
      babelHelpers: 'bundled',
      plugins: [['babel-plugin-react-compiler']],
    }),
    crx({ manifest }),
  ],
});
```

This plugin:
- Compiles `manifest.json` and all entry points in one pass
- Handles hot reload for the side panel during development
- Generates the correct `dist/` folder structure for Chrome
- Rewrites output paths so `dist/` file names differ from source names

---

## 15. Loading the Extension in Chrome

After running `pnpm build`:

1. Open Chrome → navigate to `chrome://extensions`
2. Toggle **Developer mode** ON (top right)
3. Click **Load unpacked**
4. Select the `dist/` folder from the project
5. The IQinsyt extension appears in the extensions list
6. Pin it to the toolbar (puzzle icon → pin)
7. Navigate to any sports/prediction page
8. Click the IQinsyt icon → side panel opens

**For development (watch mode):**

1. Run `pnpm dev` — Vite watches for changes
2. After each change, go to `chrome://extensions` → click the **refresh icon** on the IQinsyt card
3. The side panel auto-refreshes on React changes (hot reload) without needing to reload the whole extension

---

## 16. Testing Strategy

### Unit Tests
- Test `extractEventFromDOM()` with mock DOM structures from each supported platform
- Test the compliance pattern scanner with known violating and passing strings
- Test API key header injection + 401 handling in `api/client.ts`
- Test each error type is correctly mapped to the right UI message

```bash
npm run test        # Jest + jsdom
```

### Integration Tests
- Mock the backend with MSW (Mock Service Worker) to test full request/response cycle
- Test each error response code (401, 500) produces the correct UI state
- Test that `cached: true` renders the cache label
- Test that missing sections render `"[Data unavailable for this section]"` not blank

### Manual Test Checklist (before every release)

```
[ ] Load extension on sportsbet.com.au — event auto-detects correctly
[ ] Load extension on Kalshi — event auto-detects correctly
[ ] Test with a page where detection fails — manual input appears
[ ] Submit manual input — full flow completes
[ ] Simulate network offline — shows network error, no crash
[ ] Remove/alter API key — extension shows auth error
[ ] Confirm no green/red colours appear anywhere in UI
[ ] Confirm no predictive language appears in any rendered output
[ ] Confirm "Cached [date]" label appears on cache hit
[ ] Confirm "Data retrieval unavailable" label when flagged
[ ] Confirm all 7 sections render (even if some show [Unavailable])
```

---

*This document covers the Chrome extension in full. The web app (subscription management, manual input portal) is documented separately.*

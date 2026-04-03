# IQinsyt Web App — Full Architecture & Developer Guide

> **Scope:** This document covers the IQinsyt web app only — a companion website to the Chrome extension. It handles user registration, authentication, subscription management, dashboard, account settings, and the marketing landing page. The Chrome extension is documented separately in `architecture.md`.

---

## Table of Contents

1. [What Is This Web App?](#1-what-is-this-web-app)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Project Structure](#3-project-structure)
4. [Pages & Routes](#4-pages--routes)
5. [Authentication Flow](#5-authentication-flow)
6. [Extension Connection Flow](#6-extension-connection-flow)
7. [Subscription & Billing](#7-subscription--billing)
8. [Dashboard](#8-dashboard)
9. [State Management](#9-state-management)
10. [API Client](#10-api-client)
11. [Design Rules](#11-design-rules)
12. [CSS Approach](#12-css-approach)
13. [Build & Development Setup](#13-build--development-setup)
14. [Deployment](#14-deployment)
15. [Testing Strategy](#15-testing-strategy)

---

## 1. What Is This Web App?

IQinsyt is a **neutral AI-powered research utility** delivered as a Chrome extension. The web app is the companion website that enables users to:

- Create an account and log in
- Connect their browser account to the Chrome extension
- View usage stats and analysis history
- Manage their subscription and billing
- Manage their account settings

**What this web app is NOT:**
- Not a research tool itself — it does not call `/v1/insight` or display sports research output
- Not server-side rendered — it is a plain Vite SPA; there is no Next.js, no SSR, no server components
- Not a Chrome extension or WebExtension — it runs in an ordinary browser tab
- Not a mobile app — it targets desktop browsers only (the extension only runs on desktop Chrome)

**What this web app IS:**
- A single-page application (SPA) built with Vite + React 19 + TypeScript
- A static site deployed to Netlify or Vercel from the `dist/` output folder
- The only place users create accounts, manage subscriptions, and pair the extension to their account

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER'S BROWSER                                   │
│                                                                           │
│   IQinsyt Web App (SPA — iqinsyt.com)                                    │
│   ┌────────────────────────────────────────────────────────┐             │
│   │  React Router v6                                        │             │
│   │  ├── /                (Landing)                         │             │
│   │  ├── /register        (Registration)                    │             │
│   │  ├── /login           (Login)                           │             │
│   │  ├── /auth/callback   (Google OAuth return)             │             │
│   │  ├── /dashboard       (Usage & history)  [auth]         │             │
│   │  ├── /connect         (Extension pairing) [auth]        │             │
│   │  ├── /pricing         (Plan comparison)                 │             │
│   │  ├── /billing/success (Stripe success redirect) [auth]  │             │
│   │  ├── /billing/cancel  (Stripe cancel redirect)          │             │
│   │  └── /account         (Settings) [auth]                 │             │
│   │                                                          │             │
│   │  AppContext (useReducer + useContext)                    │             │
│   │  localStorage  ←──  JWT access + refresh tokens         │             │
│   └──────────────────────────┬─────────────────────────────┘             │
│                               │ window.postMessage                        │
│                               ▼                                           │
│   Chrome Extension (installed separately)                                 │
│   └── content script listens for auth-code message                       │
└────────────────────────────────┬──────────────────────────────────────────┘
                                 │ HTTPS + JWT
                                 ▼
                    ┌────────────────────────┐
                    │    api.iqinsyt.com      │
                    │  (Python / FastAPI)     │
                    ├────────────────────────┤
                    │ POST /v1/auth/register  │
                    │ POST /v1/auth/login     │
                    │ POST /v1/auth/refresh   │
                    │ GET  /v1/user/me        │
                    │ GET  /v1/user/plan      │
                    │ POST /v1/user/auth-code │
                    │ POST /v1/billing/...    │
                    └────────────┬───────────┘
                                 │
                    ┌────────────┴───────────┐
                    │       Stripe           │
                    │  (Checkout, webhooks)  │
                    └────────────────────────┘
```

---

## 3. Project Structure

```
iqinsyt-webapp/
├── public/
│   ├── favicon.ico
│   └── og-image.png              # Open Graph image for landing page
│
├── src/
│   ├── main.tsx                  # Vite entry point — renders <App /> into #root
│   ├── App.tsx                   # Root component: router + context provider
│   │
│   ├── pages/
│   │   ├── Landing.tsx           # / — marketing homepage
│   │   ├── Register.tsx          # /register
│   │   ├── Login.tsx             # /login
│   │   ├── OAuthCallback.tsx     # /auth/callback — Google OAuth return
│   │   ├── Dashboard.tsx         # /dashboard [auth required]
│   │   ├── Connect.tsx           # /connect [auth required]
│   │   ├── Pricing.tsx           # /pricing
│   │   ├── BillingSuccess.tsx    # /billing/success [auth required]
│   │   ├── BillingCancel.tsx     # /billing/cancel
│   │   └── Account.tsx           # /account [auth required]
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── NavBar.tsx        # Top navigation bar
│   │   │   ├── Footer.tsx        # Site footer
│   │   │   └── PageShell.tsx     # Wraps authenticated pages (NavBar + main + Footer)
│   │   │
│   │   ├── auth/
│   │   │   ├── AuthForm.tsx      # Shared email/password form used by Register + Login
│   │   │   ├── GoogleButton.tsx  # "Continue with Google" OAuth button
│   │   │   └── RequireAuth.tsx   # Route guard component — redirects to /login if not authed
│   │   │
│   │   ├── dashboard/
│   │   │   ├── UsageBar.tsx      # Visual usage meter (queries used / total)
│   │   │   ├── HistoryList.tsx   # List of recent analysis events
│   │   │   └── HistoryItem.tsx   # Single row: event title + date + cached badge
│   │   │
│   │   ├── connect/
│   │   │   ├── ConnectButton.tsx # "Connect Extension" CTA
│   │   │   ├── CodeDisplay.tsx   # Shows the one-time code for manual paste
│   │   │   └── ConnectStatus.tsx # "Connected" / "Not connected" indicator
│   │   │
│   │   ├── pricing/
│   │   │   ├── PricingCard.tsx   # One card per plan (free / starter / pro)
│   │   │   └── FeatureRow.tsx    # A single feature row inside a pricing card
│   │   │
│   │   └── shared/
│   │       ├── Button.tsx        # Reusable button (primary / ghost / danger variants)
│   │       ├── Input.tsx         # Reusable labelled text input
│   │       ├── Badge.tsx         # Inline status badge
│   │       ├── Spinner.tsx       # Loading spinner
│   │       ├── ErrorMessage.tsx  # Inline error text block
│   │       └── Modal.tsx         # Generic modal overlay
│   │
│   ├── context/
│   │   ├── AppContext.tsx        # createContext + AppProvider (useReducer wrapper)
│   │   └── useAppContext.ts      # Hook to consume AppContext (throws if used outside provider)
│   │
│   ├── api/
│   │   ├── client.ts             # fetch wrapper: token attachment, 401 refresh, error types
│   │   └── types.ts              # All API request/response TypeScript interfaces
│   │
│   ├── auth/
│   │   └── tokenStore.ts         # Read/write/clear JWT tokens in localStorage
│   │
│   ├── hooks/
│   │   ├── useAuth.ts            # Reads auth state from AppContext
│   │   ├── useDashboard.ts       # Fetches usage + history data
│   │   ├── useConnect.ts         # Manages extension pairing flow
│   │   └── useBilling.ts         # Initiates Stripe Checkout session
│   │
│   ├── shared/
│   │   ├── types.ts              # App-wide TypeScript types (AppState, AppAction, etc.)
│   │   └── constants.ts          # Plan tier names, feature lists, route paths
│   │
│   ├── utils/
│   │   └── jwt.ts                # Parse JWT payload without a library (atob approach)
│   │
│   └── styles/
│       ├── global.css            # Design tokens + reset + base styles
│       └── web.css               # Web-specific layout tokens (wider breakpoints, nav)
│
├── index.html                    # Vite HTML entry point
├── vite.config.ts
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── eslint.config.js
├── .env.example
├── package.json
├── pnpm-lock.yaml
└── architecture_webapp.md        # This file
```

---

## 4. Pages & Routes

| Path | Component | Auth Required | Purpose |
|---|---|---|---|
| `/` | `Landing` | No | Marketing homepage — product explanation, CTA to register/login |
| `/register` | `Register` | No | Email + password registration form; Google OAuth option |
| `/login` | `Login` | No | Email + password login; Google OAuth option |
| `/auth/callback` | `OAuthCallback` | No | Receives Google OAuth `code` param, exchanges for JWT, redirects to `/dashboard` |
| `/dashboard` | `Dashboard` | Yes | Shows usage stats, query quota, and recent analysis history |
| `/connect` | `Connect` | Yes | Extension pairing — generate one-time code, deliver to extension |
| `/pricing` | `Pricing` | No | Plan comparison table; "Upgrade" buttons launch Stripe Checkout |
| `/billing/success` | `BillingSuccess` | Yes | Stripe redirects here after successful payment; polls backend for updated plan |
| `/billing/cancel` | `BillingCancel` | No | Stripe redirects here if user abandons checkout |
| `/account` | `Account` | Yes | Change password, delete account, view current plan |

**Route guard:** `RequireAuth` is a wrapper component placed around every auth-required route. If `AppState.user.isAuthenticated` is `false`, it calls `navigate('/login', { replace: true })` immediately and renders nothing.

```tsx
// src/components/auth/RequireAuth.tsx
import { Navigate } from 'react-router-dom';
import { useAppContext } from '../../context/useAppContext';

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { state } = useAppContext();
  if (!state.user.isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
```

**Router setup in `App.tsx`:**

```tsx
// src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { RequireAuth } from './components/auth/RequireAuth';
import { Landing } from './pages/Landing';
import { Register } from './pages/Register';
import { Login } from './pages/Login';
import { OAuthCallback } from './pages/OAuthCallback';
import { Dashboard } from './pages/Dashboard';
import { Connect } from './pages/Connect';
import { Pricing } from './pages/Pricing';
import { BillingSuccess } from './pages/BillingSuccess';
import { BillingCancel } from './pages/BillingCancel';
import { Account } from './pages/Account';

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/register" element={<Register />} />
          <Route path="/login" element={<Login />} />
          <Route path="/auth/callback" element={<OAuthCallback />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/billing/cancel" element={<BillingCancel />} />
          <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
          <Route path="/connect" element={<RequireAuth><Connect /></RequireAuth>} />
          <Route path="/billing/success" element={<RequireAuth><BillingSuccess /></RequireAuth>} />
          <Route path="/account" element={<RequireAuth><Account /></RequireAuth>} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}
```

---

## 5. Authentication Flow

### 5.1 Token Storage

The web app stores tokens in `localStorage` (not `chrome.storage`, which is only available inside the extension). The token store is a plain module in `src/auth/tokenStore.ts`.

```typescript
// src/auth/tokenStore.ts

const STORAGE_KEY = 'iqinsyt_auth';

interface StoredTokens {
  accessToken: string;
  refreshToken: string;
  savedAt: number;
}

export function setTokens(accessToken: string, refreshToken: string): void {
  const tokens: StoredTokens = { accessToken, refreshToken, savedAt: Date.now() };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
}

export function getStoredTokens(): StoredTokens | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredTokens;
  } catch {
    return null;
  }
}

export function clearTokens(): void {
  localStorage.removeItem(STORAGE_KEY);
}
```

JWT payload parsing (no library needed):

```typescript
// src/utils/jwt.ts

export interface JwtPayload {
  userId: string;
  email: string;
  plan: 'free' | 'starter' | 'pro';
  exp: number; // Unix seconds
}

export function parseJwt(token: string): JwtPayload {
  const base64Url = token.split('.')[1];
  const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
  return JSON.parse(atob(base64)) as JwtPayload;
}

export function isTokenExpired(token: string): boolean {
  try {
    const { exp } = parseJwt(token);
    return exp * 1000 - Date.now() < 60_000; // expired or expiring within 60s
  } catch {
    return true;
  }
}
```

### 5.2 Registration

**Page:** `/register` → `Register.tsx`

1. User fills in email + password form (and confirms password client-side).
2. On submit, call `POST /v1/auth/register` with `{ email, password }`.
3. Backend responds with `{ accessToken, refreshToken, expiresIn }`.
4. Web app calls `setTokens(accessToken, refreshToken)`.
5. Parse JWT payload with `parseJwt` to extract `{ userId, email, plan }`.
6. Dispatch `SET_USER` action with `{ isAuthenticated: true, plan, email, userId }`.
7. `navigate('/connect')` — the first logical step after registration is pairing the extension.

**Error cases:**
- `409 Conflict` — email already exists → show "An account with this email already exists."
- `400 Bad Request` — invalid email or weak password → show backend error message
- Network failure → show "Could not reach the server. Check your connection."

**Registration request interface:**

```typescript
// src/api/types.ts

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number; // seconds
}
```

### 5.3 Login

**Page:** `/login` → `Login.tsx`

1. User fills in email + password.
2. On submit, call `POST /v1/auth/login` with `{ email, password }`.
3. Backend responds with `{ accessToken, refreshToken, expiresIn }`.
4. Web app calls `setTokens(accessToken, refreshToken)`.
5. Parse JWT payload, dispatch `SET_USER`.
6. If a `?redirect=` query param exists, navigate there. Otherwise navigate to `/dashboard`.

**Error cases:**
- `401 Unauthorized` — wrong credentials → show "Incorrect email or password."
- `404 Not Found` — account does not exist → show "No account found with this email."

### 5.4 Google OAuth

**Trigger:** User clicks `GoogleButton` on `/register` or `/login`.

**Flow:**

```
1. Web app redirects to Google OAuth consent screen:
   https://accounts.google.com/o/oauth2/v2/auth
     ?client_id=<VITE_GOOGLE_CLIENT_ID>
     &redirect_uri=https://iqinsyt.com/auth/callback
     &response_type=code
     &scope=openid email profile
     &state=<random_nonce_stored_in_sessionStorage>

2. Google redirects to https://iqinsyt.com/auth/callback?code=<code>&state=<nonce>

3. OAuthCallback.tsx:
   a. Reads `code` and `state` from URL search params.
   b. Validates state matches value stored in sessionStorage (CSRF protection).
   c. Calls POST /v1/auth/google with { code, redirectUri }.
   d. Backend exchanges code with Google, creates or fetches user, returns tokens.
   e. Web app calls setTokens(), dispatches SET_USER, navigates to /dashboard.
```

**`OAuthCallback.tsx` skeleton:**

```tsx
// src/pages/OAuthCallback.tsx
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAppContext } from '../context/useAppContext';
import { googleOAuth } from '../api/client';
import { setTokens } from '../auth/tokenStore';
import { parseJwt } from '../utils/jwt';
import { Spinner } from '../components/shared/Spinner';

export function OAuthCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { dispatch } = useAppContext();

  useEffect(() => {
    const code = params.get('code');
    const state = params.get('state');
    const savedState = sessionStorage.getItem('oauth_state');

    if (!code || state !== savedState) {
      navigate('/login?error=oauth_failed', { replace: true });
      return;
    }

    sessionStorage.removeItem('oauth_state');

    googleOAuth(code).then(({ accessToken, refreshToken }) => {
      setTokens(accessToken, refreshToken);
      const { userId, email, plan } = parseJwt(accessToken);
      dispatch({ type: 'SET_USER', payload: { isAuthenticated: true, userId, email, plan } });
      navigate('/dashboard', { replace: true });
    }).catch(() => {
      navigate('/login?error=oauth_failed', { replace: true });
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return <Spinner />;
}
```

### 5.5 App Bootstrap (Token Rehydration)

On every page load, `AppProvider` must rehydrate auth state from `localStorage` before rendering children. This prevents the flash of "not logged in" on page refresh.

```tsx
// src/context/AppContext.tsx (bootstrap logic)
import { useEffect, useReducer } from 'react';
import { getStoredTokens } from '../auth/tokenStore';
import { parseJwt, isTokenExpired } from '../utils/jwt';
import { refreshAccessToken } from '../api/client';

function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  useEffect(() => {
    const stored = getStoredTokens();
    if (!stored) return; // not logged in

    // If access token is still valid, hydrate immediately
    if (!isTokenExpired(stored.accessToken)) {
      const { userId, email, plan } = parseJwt(stored.accessToken);
      dispatch({ type: 'SET_USER', payload: { isAuthenticated: true, userId, email, plan } });
      return;
    }

    // Access token expired — attempt refresh
    refreshAccessToken(stored.refreshToken).then((newAccessToken) => {
      if (!newAccessToken) return; // refresh failed, stay logged out
      const { userId, email, plan } = parseJwt(newAccessToken);
      dispatch({ type: 'SET_USER', payload: { isAuthenticated: true, userId, email, plan } });
    });
  }, []);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}
```

### 5.6 Logout

Any component can call `logout()` from `useAuth`:

```typescript
// src/hooks/useAuth.ts
import { useAppContext } from '../context/useAppContext';
import { clearTokens } from '../auth/tokenStore';
import { useNavigate } from 'react-router-dom';

export function useAuth() {
  const { state, dispatch } = useAppContext();
  const navigate = useNavigate();

  function logout() {
    clearTokens();
    dispatch({ type: 'LOGOUT' });
    navigate('/login', { replace: true });
  }

  return { user: state.user, logout };
}
```

---

## 6. Extension Connection Flow

**Page:** `/connect` → `Connect.tsx`

After login (or at any time from the dashboard), the user connects their browser account to the Chrome extension. The extension needs a short-lived one-time code to exchange for JWT tokens on first use.

### 6.1 Full Flow

```
1. User clicks "Connect Extension" on /connect page.

2. Web app calls POST /v1/user/auth-code (authenticated request).
   Backend generates a one-time code (e.g. 6-character alphanumeric, TTL 5 minutes).
   Response: { code: "A3XK9P", expiresAt: "2026-04-02T10:35:00Z" }

3. Web app attempts automatic delivery via window.postMessage:
   window.postMessage({ type: 'IQINSYT_AUTH_CODE', code: 'A3XK9P' }, '*');

4. The extension's content script listens for this message:
   window.addEventListener('message', (event) => {
     if (event.data?.type === 'IQINSYT_AUTH_CODE') {
       chrome.runtime.sendMessage({ type: 'PAIR_WITH_CODE', code: event.data.code });
     }
   });

5. If extension is NOT installed, the postMessage is ignored.
   Web app detects this by waiting 1.5 seconds for a response message
   ({ type: 'IQINSYT_PAIR_ACK' }) from the extension.
   If no ACK arrives, fall through to the manual fallback.

6. Manual fallback:
   Web app displays the code visually in a large, monospaced box.
   User copies the code.
   User opens the extension side panel → clicks "Enter pairing code" → pastes the code.
   Extension calls POST /v1/auth/token with { code } → receives JWT tokens.
   Extension stores tokens in chrome.storage.local.

7. Connection success (either path):
   Web app shows "Extension connected successfully."
   ConnectStatus badge in the UI updates to "Connected".
```

### 6.2 Code Display Component

```tsx
// src/components/connect/CodeDisplay.tsx
interface CodeDisplayProps {
  code: string;
  expiresAt: string; // ISO timestamp
}

export function CodeDisplay({ code, expiresAt }: CodeDisplayProps) {
  const [copied, setCopied] = React.useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const expiryLabel = new Date(expiresAt).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit',
  });

  return (
    <div className="iq-code-display">
      <p className="iq-code-display__label">Enter this code in the IQinsyt extension:</p>
      <div className="iq-code-display__box">{code}</div>
      <p className="iq-code-display__expiry">Expires at {expiryLabel}</p>
      <button className="iq-btn iq-btn--ghost" onClick={handleCopy}>
        {copied ? 'Copied!' : 'Copy code'}
      </button>
    </div>
  );
}
```

### 6.3 postMessage Handshake Detail

```typescript
// src/hooks/useConnect.ts
const PAIR_TIMEOUT_MS = 1500;

export function useConnect() {
  const [phase, setPhase] = React.useState<'idle' | 'loading' | 'code' | 'success' | 'error'>('idle');
  const [code, setCode] = React.useState<string | null>(null);
  const [expiresAt, setExpiresAt] = React.useState<string | null>(null);

  async function startConnect() {
    setPhase('loading');
    try {
      const { code: newCode, expiresAt: exp } = await generateAuthCode(); // calls POST /v1/user/auth-code
      setCode(newCode);
      setExpiresAt(exp);

      // Attempt automatic delivery
      window.postMessage({ type: 'IQINSYT_AUTH_CODE', code: newCode }, '*');

      // Listen for ACK from extension
      const ack = await waitForMessage('IQINSYT_PAIR_ACK', PAIR_TIMEOUT_MS);

      if (ack) {
        setPhase('success');
      } else {
        // Extension not installed — show manual code
        setPhase('code');
      }
    } catch {
      setPhase('error');
    }
  }

  return { phase, code, expiresAt, startConnect };
}

function waitForMessage(type: string, timeoutMs: number): Promise<boolean> {
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      window.removeEventListener('message', handler);
      resolve(false);
    }, timeoutMs);

    function handler(event: MessageEvent) {
      if (event.data?.type === type) {
        clearTimeout(timer);
        window.removeEventListener('message', handler);
        resolve(true);
      }
    }

    window.addEventListener('message', handler);
  });
}
```

### 6.4 Auth Code API Types

```typescript
// src/api/types.ts (addition)
export interface AuthCodeResponse {
  code: string;       // e.g. "A3XK9P"
  expiresAt: string;  // ISO timestamp
}
```

---

## 7. Subscription & Billing

### 7.1 Plan Tier Table

| Feature | Free | Starter | Pro |
|---|---|---|---|
| Queries per month | 5 | 50 | 250 |
| AI model | GPT-4o-mini | GPT-4o-mini | GPT-4o |
| Cache access | Yes | Yes | Yes |
| Analysis history | Last 5 | Last 30 | Last 90 |
| Priority support | No | No | Yes |
| Price | $0 | $9/mo | $29/mo |

### 7.2 Pricing Page

**Page:** `/pricing` → `Pricing.tsx`

- Renders three `PricingCard` components side-by-side.
- Each card shows plan name, price, feature list, and a CTA button.
- If the user is logged in and already on a plan, their current plan card shows "Current plan" instead of an upgrade button.
- "Upgrade" button triggers the Stripe Checkout flow (see 7.3).
- If the user is not logged in, "Get started" links to `/register`.

### 7.3 Stripe Checkout Flow

```
1. User clicks "Upgrade to Starter" (or Pro) on /pricing.

2. Web app calls POST /v1/billing/checkout with { plan: 'starter' }.
   Backend (FastAPI) calls Stripe API to create a Checkout Session.
   Backend returns: { checkoutUrl: "https://checkout.stripe.com/pay/cs_..." }

3. Web app calls: window.location.href = checkoutUrl
   (full page redirect to Stripe — this is intentional; do NOT use an iframe)

4. User completes payment on Stripe's hosted checkout page.

5a. On success: Stripe redirects to https://iqinsyt.com/billing/success?session_id=<id>
5b. On cancel:  Stripe redirects to https://iqinsyt.com/billing/cancel

6. BillingSuccess.tsx:
   a. Reads session_id from URL params.
   b. Calls GET /v1/billing/session?session_id=<id> to verify completion.
   c. Shows "Payment confirmed — your plan has been upgraded."
   d. Calls GET /v1/user/plan to get updated plan.
   e. Dispatches SET_USER with updated plan.
   f. Shows "Go to dashboard" CTA.
```

**Important:** The actual plan update happens via Stripe webhook on the backend. The web app does not need to trigger this — it only polls to confirm the update has landed.

### 7.4 Billing API Types

```typescript
// src/api/types.ts (additions)

export interface CheckoutRequest {
  plan: 'starter' | 'pro';
}

export interface CheckoutResponse {
  checkoutUrl: string;
}

export interface BillingSessionResponse {
  status: 'complete' | 'pending' | 'failed';
  plan: 'free' | 'starter' | 'pro';
}
```

### 7.5 Post-Payment Plan Polling

`BillingSuccess.tsx` polls `GET /v1/billing/session?session_id=<id>` up to 5 times at 2-second intervals until `status === 'complete'`. If it does not confirm within 10 seconds, show: "Your payment was received. Your plan update may take a moment — refresh the dashboard shortly."

```typescript
// Polling logic in BillingSuccess.tsx
async function pollForCompletion(sessionId: string): Promise<BillingSessionResponse> {
  for (let attempt = 0; attempt < 5; attempt++) {
    const result = await fetchBillingSession(sessionId);
    if (result.status === 'complete') return result;
    await new Promise(r => setTimeout(r, 2000));
  }
  throw new Error('Timed out waiting for payment confirmation');
}
```

### 7.6 Cancel / Downgrade

Subscription cancellation (downgrade to free) is handled from the `/account` page. The user clicks "Cancel subscription", web app calls `POST /v1/billing/cancel`, and shows confirmation. The plan reverts to `free` at the end of the current billing period.

---

## 8. Dashboard

**Page:** `/dashboard` → `Dashboard.tsx`

### 8.1 What Is Displayed

| Section | Data | API Endpoint |
|---|---|---|
| Plan badge | Current plan (`free` / `starter` / `pro`) | `GET /v1/user/plan` |
| Usage bar | Queries used this period, total allowed | `GET /v1/user/plan` |
| Reset date | When the monthly quota resets | `GET /v1/user/plan` |
| Recent analyses | List of events analysed, date, cached status | `GET /v1/user/history` |
| Extension status | Whether extension is linked | `GET /v1/user/me` |

### 8.2 API Response Types

```typescript
// src/api/types.ts

export interface UserPlanResponse {
  plan: 'free' | 'starter' | 'pro';
  queriesUsed: number;
  queriesTotal: number;
  resetsAt: string; // ISO timestamp
}

export interface HistoryItem {
  requestId: string;
  eventTitle: string;
  eventSource: string;
  queriedAt: string;  // ISO timestamp
  cached: boolean;
}

export interface UserHistoryResponse {
  items: HistoryItem[];
  total: number;
}

export interface UserMeResponse {
  userId: string;
  email: string;
  plan: 'free' | 'starter' | 'pro';
  extensionLinked: boolean;
  createdAt: string;
}
```

### 8.3 Data Fetching

`useDashboard` fetches all dashboard data on mount and stores it in local component state (not AppContext — this data is not needed globally).

```typescript
// src/hooks/useDashboard.ts
import { useState, useEffect } from 'react';
import { fetchUserPlan, fetchUserHistory, fetchUserMe } from '../api/client';
import type { UserPlanResponse, UserHistoryResponse, UserMeResponse } from '../api/types';

interface DashboardData {
  plan: UserPlanResponse | null;
  history: UserHistoryResponse | null;
  me: UserMeResponse | null;
  loading: boolean;
  error: string | null;
}

export function useDashboard(): DashboardData {
  const [data, setData] = useState<DashboardData>({
    plan: null, history: null, me: null, loading: true, error: null,
  });

  useEffect(() => {
    Promise.all([fetchUserPlan(), fetchUserHistory(), fetchUserMe()])
      .then(([plan, history, me]) => {
        setData({ plan, history, me, loading: false, error: null });
      })
      .catch((e) => {
        setData(prev => ({ ...prev, loading: false, error: e.message }));
      });
  }, []);

  return data;
}
```

### 8.4 Usage Bar Rendering

```
[ ████████░░░░░░░░░░░░ ] 23 / 50 queries used  ·  Resets 1 May 2026
```

The fill percentage is `(queriesUsed / queriesTotal) * 100`. The bar uses a neutral accent colour, never green/red.

```tsx
// src/components/dashboard/UsageBar.tsx
interface UsageBarProps {
  used: number;
  total: number;
  resetsAt: string;
}

export function UsageBar({ used, total, resetsAt }: UsageBarProps) {
  const pct = Math.min((used / total) * 100, 100);
  const resetLabel = new Date(resetsAt).toLocaleDateString(undefined, {
    day: 'numeric', month: 'long', year: 'numeric',
  });

  return (
    <div className="iq-usage">
      <div className="iq-usage__bar-track">
        <div className="iq-usage__bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="iq-usage__label">
        {used} / {total} queries used &middot; Resets {resetLabel}
      </p>
    </div>
  );
}
```

### 8.5 History List

`HistoryList` renders up to the plan-allowed history count (5 / 30 / 90 items). Each `HistoryItem` row shows:
- Event title (truncated to 60 chars with ellipsis if longer)
- Source hostname (e.g. `sportsbet.com.au`)
- Date analysed (formatted as `2 Apr 2026`)
- "Cached" badge if `cached === true`

If `history.items` is empty, show: "No analyses yet. Open the extension on a sports page to get started."

---

## 9. State Management

### 9.1 Global vs Local State

**AppContext (global state):** Only what every part of the app needs:
- Whether the user is authenticated
- User's identity (userId, email, plan)
- A global error/notification slot (for session expiry etc.)

**Local component state:** Everything else:
- Dashboard data (plan, history, profile)
- Connect flow phase + code
- Form field values and validation errors
- Billing session polling status

The rule: if only one page or component needs it, it stays in `useState` or `useReducer` inside that component/hook.

### 9.2 AppState Shape

```typescript
// src/shared/types.ts

export interface UserInfo {
  isAuthenticated: boolean;
  userId: string | null;
  email: string | null;
  plan: 'free' | 'starter' | 'pro' | null;
}

export interface AppState {
  user: UserInfo;
  globalError: string | null;      // session expiry, network-level errors
  authLoading: boolean;            // true while rehydrating tokens on bootstrap
}

export const initialState: AppState = {
  user: {
    isAuthenticated: false,
    userId: null,
    email: null,
    plan: null,
  },
  globalError: null,
  authLoading: true,
};
```

### 9.3 AppAction Union

```typescript
// src/shared/types.ts

export type AppAction =
  | { type: 'SET_USER'; payload: UserInfo }
  | { type: 'LOGOUT' }
  | { type: 'SET_GLOBAL_ERROR'; payload: string }
  | { type: 'CLEAR_GLOBAL_ERROR' }
  | { type: 'AUTH_LOADING_DONE' };
```

### 9.4 Reducer

```typescript
// src/context/AppContext.tsx

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_USER':
      return { ...state, user: action.payload, authLoading: false };
    case 'LOGOUT':
      return { ...state, user: initialState.user, globalError: null };
    case 'SET_GLOBAL_ERROR':
      return { ...state, globalError: action.payload };
    case 'CLEAR_GLOBAL_ERROR':
      return { ...state, globalError: null };
    case 'AUTH_LOADING_DONE':
      return { ...state, authLoading: false };
    default:
      return state;
  }
}
```

### 9.5 Context Provider

```tsx
// src/context/AppContext.tsx
import { createContext, useReducer } from 'react';
import type { Dispatch } from 'react';
import type { AppState, AppAction } from '../shared/types';

interface AppContextValue {
  state: AppState;
  dispatch: Dispatch<AppAction>;
}

export const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  // Bootstrap logic runs in a useEffect here (see Section 5.5)
  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}
```

```typescript
// src/context/useAppContext.ts
import { useContext } from 'react';
import { AppContext } from './AppContext';

export function useAppContext() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppContext must be used inside <AppProvider>');
  return ctx;
}
```

---

## 10. API Client

### 10.1 Structure

All backend calls go through `src/api/client.ts`. It handles:
- Base URL from `import.meta.env.VITE_API_URL`
- Attaching JWT `Authorization` header
- Proactively refreshing tokens before expiry (same 60-second window as the extension)
- Throwing typed errors: `AuthError`, `SubscriptionError`, `ApiError`
- Dispatching `LOGOUT` action on unrecoverable 401s

### 10.2 Client Implementation

```typescript
// src/api/client.ts
import { getStoredTokens, setTokens, clearTokens } from '../auth/tokenStore';
import { isTokenExpired, parseJwt } from '../utils/jwt';
import type {
  AuthResponse, RegisterRequest, CheckoutRequest, CheckoutResponse,
  UserPlanResponse, UserHistoryResponse, UserMeResponse,
  AuthCodeResponse, BillingSessionResponse,
} from './types';

const BASE_URL = import.meta.env.VITE_API_URL as string;

// ─── Error Types ──────────────────────────────────────────────────────────────

export class AuthError extends Error {
  constructor(message: string) { super(message); this.name = 'AuthError'; }
}

export class SubscriptionError extends Error {
  constructor(message: string) { super(message); this.name = 'SubscriptionError'; }
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// ─── Token Refresh ────────────────────────────────────────────────────────────

export async function refreshAccessToken(refreshToken: string): Promise<string | null> {
  const response = await fetch(`${BASE_URL}/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refreshToken }),
  });

  if (!response.ok) {
    clearTokens();
    return null;
  }

  const data = await response.json() as AuthResponse;
  setTokens(data.accessToken, data.refreshToken);
  return data.accessToken;
}

// ─── Authenticated Fetch ──────────────────────────────────────────────────────

async function getValidAccessToken(): Promise<string> {
  const stored = getStoredTokens();
  if (!stored) throw new AuthError('Not authenticated');

  if (isTokenExpired(stored.accessToken)) {
    const newToken = await refreshAccessToken(stored.refreshToken);
    if (!newToken) throw new AuthError('Session expired');
    return newToken;
  }

  return stored.accessToken;
}

async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getValidAccessToken();

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...init.headers,
    },
  });

  if (response.status === 401) throw new AuthError('Session expired');
  if (response.status === 402) throw new SubscriptionError('Plan inactive');
  if (!response.ok) throw new ApiError(`Request failed: ${response.status}`, response.status);

  return response;
}

// ─── Auth Endpoints ───────────────────────────────────────────────────────────

export async function register(body: RegisterRequest): Promise<AuthResponse> {
  const response = await fetch(`${BASE_URL}/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new ApiError(`Registration failed: ${response.status}`, response.status);
  return response.json() as Promise<AuthResponse>;
}

export async function login(body: RegisterRequest): Promise<AuthResponse> {
  const response = await fetch(`${BASE_URL}/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new ApiError(`Login failed: ${response.status}`, response.status);
  return response.json() as Promise<AuthResponse>;
}

export async function googleOAuth(code: string): Promise<AuthResponse> {
  const response = await fetch(`${BASE_URL}/v1/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, redirectUri: `${window.location.origin}/auth/callback` }),
  });
  if (!response.ok) throw new ApiError(`OAuth failed: ${response.status}`, response.status);
  return response.json() as Promise<AuthResponse>;
}

// ─── User Endpoints ───────────────────────────────────────────────────────────

export async function fetchUserMe(): Promise<UserMeResponse> {
  const response = await authedFetch('/v1/user/me');
  return response.json() as Promise<UserMeResponse>;
}

export async function fetchUserPlan(): Promise<UserPlanResponse> {
  const response = await authedFetch('/v1/user/plan');
  return response.json() as Promise<UserPlanResponse>;
}

export async function fetchUserHistory(): Promise<UserHistoryResponse> {
  const response = await authedFetch('/v1/user/history');
  return response.json() as Promise<UserHistoryResponse>;
}

export async function generateAuthCode(): Promise<AuthCodeResponse> {
  const response = await authedFetch('/v1/user/auth-code', { method: 'POST' });
  return response.json() as Promise<AuthCodeResponse>;
}

// ─── Billing Endpoints ────────────────────────────────────────────────────────

export async function createCheckoutSession(body: CheckoutRequest): Promise<CheckoutResponse> {
  const response = await authedFetch('/v1/billing/checkout', {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return response.json() as Promise<CheckoutResponse>;
}

export async function fetchBillingSession(sessionId: string): Promise<BillingSessionResponse> {
  const response = await authedFetch(`/v1/billing/session?session_id=${encodeURIComponent(sessionId)}`);
  return response.json() as Promise<BillingSessionResponse>;
}

export async function cancelSubscription(): Promise<void> {
  await authedFetch('/v1/billing/cancel', { method: 'POST' });
}
```

### 10.3 Global 401 Handling

When any `authedFetch` call throws `AuthError`, page-level components catch it and dispatch `LOGOUT`:

```typescript
// Pattern used in every page-level hook
try {
  const data = await fetchUserPlan();
  // ...
} catch (e) {
  if (e instanceof AuthError) {
    dispatch({ type: 'LOGOUT' });
    // React Router will redirect to /login via RequireAuth
  } else {
    setError('Something went wrong. Try again.');
  }
}
```

---

## 11. Design Rules

These rules apply to every pixel of the web app. They match the Chrome extension's design rules exactly.

**Neutrality (non-negotiable):**
- No green or red colours anywhere in the UI — these colours imply positive/negative outcomes
- No directional arrows (up/down triangles) that imply outcome direction
- No percentage chances, odds, or probability language — even in marketing copy
- No language that could be read as a prediction or recommendation

**Visual language:**
- Neutral palette: whites, greys, and the accent purple (`#aa3bff`)
- Font: system font stack only — `font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- No third-party UI component libraries (no MUI, no Radix, no shadcn/ui)
- No Tailwind CSS — all styling via CSS custom properties as defined in Section 12

**Tone in copy:**
- Describe what the tool does, not what it "predicts"
- Use: "Research", "Analysis", "Factual context", "Data"
- Avoid: "Tips", "Picks", "Predictions", "Odds", "Forecasts", "Insights into who will win"

**Accessible defaults:**
- All interactive elements have visible focus rings (use `var(--accent-border)` for focus outlines)
- Form inputs have associated `<label>` elements
- `aria-live` regions for dynamic status changes (connection success, form errors)
- Never hide content with `display: none` for screen readers — use `aria-hidden` where appropriate

---

## 12. CSS Approach

### 12.1 Design Tokens

The web app imports and extends the same CSS custom property tokens as the Chrome extension. The extension's tokens are scoped for a 400px side panel. The web app adds additional tokens for wider viewport layouts.

**`src/styles/global.css`** — identical token set to the extension's `src/index.css`:

```css
/* ─── Core Design Tokens (shared with extension) ─────────────────────────── */

:root {
  --text:          #6b6375;
  --text-h:        #08060d;
  --bg:            #fff;
  --bg-subtle:     #f9f8fb;
  --border:        #e5e4e7;
  --code-bg:       #f4f3ec;
  --accent:        #aa3bff;
  --accent-bg:     rgba(170, 59, 255, 0.08);
  --accent-border: rgba(170, 59, 255, 0.3);
  --shadow-sm:     0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow:        rgba(0,0,0,0.08) 0 4px 12px, rgba(0,0,0,0.04) 0 2px 4px;
  --radius:        10px;
  --radius-sm:     6px;

  --sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --mono: ui-monospace, Consolas, monospace;
}

@media (prefers-color-scheme: dark) {
  :root {
    --text:          #9ca3af;
    --text-h:        #f3f4f6;
    --bg:            #16171d;
    --bg-subtle:     #1c1d25;
    --border:        #2e303a;
    --code-bg:       #1f2028;
    --accent:        #c084fc;
    --accent-bg:     rgba(192, 132, 252, 0.1);
    --accent-border: rgba(192, 132, 252, 0.3);
    --shadow-sm:     0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2);
    --shadow:        rgba(0,0,0,0.4) 0 4px 12px, rgba(0,0,0,0.2) 0 2px 4px;
  }
}
```

**`src/styles/web.css`** — web-specific additions for wider layouts:

```css
/* ─── Web Layout Tokens ──────────────────────────────────────────────────── */

:root {
  /* Layout widths */
  --content-max:      1100px;   /* max-width for page content */
  --content-padding:  24px;     /* horizontal padding on small screens */
  --nav-height:       60px;     /* top navigation bar height */

  /* Web-specific spacing scale */
  --space-xs:   4px;
  --space-sm:   8px;
  --space-md:   16px;
  --space-lg:   32px;
  --space-xl:   64px;
  --space-2xl:  96px;

  /* Pricing card */
  --card-min-width: 280px;

  /* Form max width */
  --form-max: 440px;
}
```

### 12.2 Class Naming Convention

All CSS classes use the `iq-` prefix (same as the extension). Web-specific classes use `iq-web-` to distinguish them from extension classes:

```
iq-nav            → top navigation bar
iq-nav__logo      → logo inside nav
iq-nav__links     → link group in nav

iq-page           → full-page wrapper
iq-page__hero     → hero section
iq-page__section  → generic content section

iq-form           → auth form container
iq-form__field    → label + input pair
iq-form__error    → inline error message

iq-pricing-grid   → pricing cards grid container
iq-pricing-card   → individual plan card
iq-pricing-card--highlight → featured/recommended plan card

iq-usage          → usage bar container
iq-history        → history list

iq-code-display   → pairing code display box
```

### 12.3 Responsive Layout

The web app targets desktop-first. Breakpoints:

| Breakpoint | Width | Behaviour |
|---|---|---|
| Mobile | < 640px | Single-column, hamburger nav |
| Tablet | 640px – 1024px | Single-column content, full nav |
| Desktop | > 1024px | Two/three column grids, max-width container |

Implement with CSS Grid and `@media (min-width: ...)` — no utility classes.

---

## 13. Build & Development Setup

### 13.1 Prerequisites

```
Node.js >= 20.x
pnpm >= 9.x
```

### 13.2 Initial Setup

```bash
git clone <repo>
cd iqinsyt-webapp
pnpm install
cp .env.example .env
```

### 13.3 Environment Variables

**`.env.example`:**

```bash
# Backend API base URL (no trailing slash)
VITE_API_URL=https://api.iqinsyt.com

# Stripe publishable key (safe to expose in frontend)
VITE_STRIPE_KEY=pk_live_...

# Google OAuth client ID
VITE_GOOGLE_CLIENT_ID=<your-google-client-id>.apps.googleusercontent.com

# For local development override:
# VITE_API_URL=http://localhost:8000
# VITE_STRIPE_KEY=pk_test_...
```

**All env vars must be prefixed with `VITE_`** — Vite only exposes variables with this prefix to the browser bundle. They are embedded at build time.

**Never put secret keys here.** The Stripe *secret* key, Google *client secret*, and JWT signing secret live only on the backend. The `VITE_STRIPE_KEY` is the *publishable* key, which is safe.

### 13.4 `vite.config.ts`

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  server: {
    port: 5173,
  },
});
```

No `@crxjs/vite-plugin` — that is only for the Chrome extension. This is a standard Vite SPA config.

### 13.5 `tsconfig.app.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

### 13.6 `package.json` Scripts

```json
{
  "scripts": {
    "dev":       "vite",
    "build":     "tsc -b && vite build",
    "preview":   "vite preview",
    "typecheck": "tsc --noEmit",
    "lint":      "eslint .",
    "test":      "vitest run",
    "test:watch": "vitest"
  }
}
```

### 13.7 Key Dependencies

```json
{
  "dependencies": {
    "react": "^19.x",
    "react-dom": "^19.x",
    "react-router-dom": "^6.x"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^6.x",
    "@types/react": "^19.x",
    "@types/react-dom": "^19.x",
    "typescript": "~5.9.x",
    "vite": "^8.x",
    "vitest": "^2.x",
    "@testing-library/react": "^16.x",
    "@testing-library/user-event": "^14.x",
    "msw": "^2.x",
    "eslint": "^9.x",
    "eslint-plugin-react-hooks": "^5.x",
    "globals": "^15.x",
    "typescript-eslint": "^8.x"
  }
}
```

Install with `pnpm add react react-dom react-router-dom` and `pnpm add -D` for dev deps. **Do not use npm or yarn** — the lockfile is `pnpm-lock.yaml`.

### 13.8 Development Commands

```bash
# Start dev server (http://localhost:5173)
pnpm dev

# Production build
pnpm build

# Preview production build locally
pnpm preview

# Type check without emitting
pnpm typecheck

# Run tests once
pnpm test

# Run tests in watch mode
pnpm test:watch
```

---

## 14. Deployment

### 14.1 Build Output

```bash
pnpm build
# Outputs static files to dist/
# dist/
#   index.html
#   assets/
#     index-<hash>.js
#     index-<hash>.css
```

The `dist/` folder is a self-contained static site — no server required.

### 14.2 SPA Redirect Rule (Critical)

Because this is a client-side SPA using React Router, all routes (e.g. `/dashboard`, `/login`) are handled by JavaScript — they are not real server paths. Any direct visit to a non-root URL will 404 unless the hosting platform is told to serve `index.html` for all paths.

**This rule must be configured on the hosting platform:**

```
/* → /index.html (HTTP 200)
```

**Netlify (`public/_redirects` file):**

```
/* /index.html 200
```

Place this file in the `public/` directory. Vite copies everything in `public/` to `dist/` as-is, so `dist/_redirects` will be present after build.

**Netlify `netlify.toml` (alternative / preferred):**

```toml
[build]
  command   = "pnpm build"
  publish   = "dist"

[[redirects]]
  from   = "/*"
  to     = "/index.html"
  status = 200
```

**Vercel (`vercel.json`):**

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ],
  "buildCommand": "pnpm build",
  "outputDirectory": "dist"
}
```

### 14.3 Environment Variables in Production

On Netlify or Vercel, set environment variables through the platform UI (not committed to the repo):

```
VITE_API_URL           = https://api.iqinsyt.com
VITE_STRIPE_KEY        = pk_live_...
VITE_GOOGLE_CLIENT_ID  = <id>.apps.googleusercontent.com
```

Variables are embedded at build time. Changing a variable requires a new build.

### 14.4 Domain & SSL

- Primary domain: `iqinsyt.com`
- The OAuth callback redirect URI (`https://iqinsyt.com/auth/callback`) must be registered in Google Cloud Console.
- The Stripe Checkout success/cancel URLs (`https://iqinsyt.com/billing/success`, `https://iqinsyt.com/billing/cancel`) must match the backend's Stripe session config.
- SSL is handled automatically by Netlify/Vercel for custom domains.

### 14.5 Deploy Checklist

```
[ ] VITE_API_URL points to production backend (not localhost)
[ ] VITE_STRIPE_KEY is the live publishable key (not test)
[ ] VITE_GOOGLE_CLIENT_ID is registered with the correct redirect URI
[ ] SPA redirect rule is configured (_redirects or vercel.json)
[ ] Google Cloud Console has https://iqinsyt.com/auth/callback in Authorised redirect URIs
[ ] Stripe Dashboard has https://iqinsyt.com/billing/success and /billing/cancel as allowed redirect URLs
[ ] Backend CORS allows https://iqinsyt.com origin
[ ] No console.log statements shipping to production (check with lint rule no-console)
```

---

## 15. Testing Strategy

### 15.1 Unit Tests (Vitest + React Testing Library)

Run with `pnpm test`. Test files live alongside source files as `*.test.ts` / `*.test.tsx`.

**Token store (`src/auth/tokenStore.test.ts`):**
- `setTokens` writes a valid JSON object to localStorage
- `getStoredTokens` returns null when localStorage is empty
- `clearTokens` removes the key from localStorage

**JWT utils (`src/utils/jwt.test.ts`):**
- `parseJwt` correctly decodes a known token and returns expected payload fields
- `isTokenExpired` returns `true` for a token with `exp` in the past
- `isTokenExpired` returns `true` for a token expiring within 60 seconds
- `isTokenExpired` returns `false` for a token with plenty of time remaining
- `isTokenExpired` returns `true` for a malformed token string

**Reducer (`src/shared/reducer.test.ts`):**
- `SET_USER` sets `isAuthenticated: true` and stores user fields
- `LOGOUT` resets user to initial state
- `SET_GLOBAL_ERROR` sets `globalError`
- `CLEAR_GLOBAL_ERROR` clears `globalError`

**`RequireAuth` component:**
- Renders children when `isAuthenticated: true`
- Redirects to `/login` when `isAuthenticated: false`

**`UsageBar` component:**
- Renders correct percentage width for 23/50 (46%)
- Renders 100% fill when `used >= total`
- Formats reset date correctly

### 15.2 Integration Tests (MSW)

Use Mock Service Worker (`msw`) to intercept `fetch` calls and return controlled responses.

Set up a shared handler file at `src/__mocks__/handlers.ts`:

```typescript
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.post('/v1/auth/login', () => HttpResponse.json({
    accessToken: 'eyJ...mock.token',
    refreshToken: 'refresh.token',
    expiresIn: 3600,
  })),
  http.get('/v1/user/plan', () => HttpResponse.json({
    plan: 'starter',
    queriesUsed: 23,
    queriesTotal: 50,
    resetsAt: '2026-05-01T00:00:00Z',
  })),
  // ... etc
];
```

**Integration test scenarios:**
- Login form: submits credentials, receives tokens, stores in localStorage, navigates to `/dashboard`
- Login form: shows "Incorrect email or password" on 401 response
- `OAuthCallback`: valid state + code → calls `/v1/auth/google` → stores tokens → navigates to `/dashboard`
- `OAuthCallback`: mismatched state → navigates to `/login?error=oauth_failed`
- Dashboard: renders `UsageBar` with correct values from mock plan response
- Dashboard: renders history items with correct event titles, dates, cached badges
- Connect page: clicking "Connect Extension" calls `/v1/user/auth-code`, fires `postMessage`
- Connect page: shows `CodeDisplay` when no extension ACK received within timeout
- `BillingSuccess`: polls `/v1/billing/session` until `status === 'complete'`, updates plan in context
- `Account`: clicking "Cancel subscription" calls `/v1/billing/cancel`
- 401 on any authed request: clears tokens, user is redirected to `/login`

### 15.3 Manual Test Checklist (Before Every Release)

```
AUTH
[ ] Register with a new email — tokens stored, redirected to /connect
[ ] Register with duplicate email — error message shown, not a crash
[ ] Login with correct credentials — redirected to /dashboard
[ ] Login with wrong password — "Incorrect email or password" shown
[ ] Google OAuth happy path — redirected to /dashboard, plan badge correct
[ ] Google OAuth with mismatched state — redirected to /login with error
[ ] Refresh page while logged in — auth state rehydrated, no flash of /login
[ ] Access /dashboard while logged out — redirected to /login
[ ] Logout — tokens cleared, redirected to /login, /dashboard no longer accessible

EXTENSION CONNECTION
[ ] Click "Connect Extension" with extension installed — automatic connection, success shown
[ ] Click "Connect Extension" without extension installed — code displayed after 1.5s timeout
[ ] Copy button copies code to clipboard
[ ] Code shows correct expiry time
[ ] Expired code rejected by extension (error handled gracefully in extension)

SUBSCRIPTION & BILLING
[ ] /pricing renders all three plan cards with correct prices and features
[ ] "Upgrade" button redirects to Stripe Checkout (do not confirm payment in test run — check URL)
[ ] /billing/cancel shows cancellation message without error
[ ] No green or red colours appear anywhere on /pricing

DASHBOARD
[ ] Usage bar fills correct proportion for current usage
[ ] History list shows event titles, dates, and cached badges
[ ] Empty history state shows expected placeholder message
[ ] Plan badge matches actual account plan

DESIGN COMPLIANCE
[ ] No green or red colours appear anywhere in the app
[ ] No directional arrows appear in any UI element
[ ] No predictive or recommendation language in any copy
[ ] System font renders correctly (no web font loading delays)
[ ] Dark mode renders correctly (all tokens switch)
[ ] Focus rings visible on all interactive elements when tabbing

NAVIGATION
[ ] Direct URL to /dashboard while logged in loads correctly (SPA redirect working)
[ ] Direct URL to /dashboard while logged out redirects to /login
[ ] Back/forward browser navigation works correctly within the app
```

---

*This document covers the IQinsyt web app in full. The Chrome extension is documented separately in `architecture.md`.*

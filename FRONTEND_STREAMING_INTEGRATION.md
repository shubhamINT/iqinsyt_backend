# Frontend Migration Guide: `/v1/research` Streaming (React + Vite)

This guide explains exactly what your frontend must change to work with the new streaming backend contract.

## 1. What Changed

`POST /v1/research` no longer returns one JSON body.

It now returns an **SSE stream** (`Content-Type: text/event-stream`) with multiple events:

- `research.started`
- `research.progress`
- `research.completed`
- `research.error`

You must read the response stream incrementally and handle events as they arrive.

## 2. Request Contract

URL:

```http
POST /v1/research
```

Headers:

```http
Content-Type: application/json
Accept: text/event-stream
X-API-Key: <your-api-key>
```

Body:

```json
{
  "eventTitle": "string (1-500 chars)",
  "eventSource": "string (1-253 chars)",
  "timestamp": 1743638400000
}
```

Notes:

- Use `fetch`, not `EventSource`, because this is a **POST** stream.
- Keep using `X-API-Key` in frontend for forward compatibility.

## 3. Stream Event Contract

Each event frame is standard SSE:

```text
event: <event_name>
data: <json>

```

### `research.started`

```json
{
  "request_id": "uuid",
  "stage": "request.accepted",
  "message": "Research request accepted"
}
```

### `research.progress`

```json
{
  "request_id": "uuid",
  "stage": "cache.lookup.started",
  "message": "Checking cache for existing research",
  "meta": {
    "attempt": 1,
    "max_attempts": 3,
    "data_retrieval_available": true
  }
}
```

`meta` is optional and depends on stage.

### `research.completed`

This is your final successful payload. Shape is the same envelope you previously received as plain JSON:

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
    "generatedAt": "2026-04-07T12:00:00Z"
  },
  "request_id": "uuid",
  "timestamp": "2026-04-07T12:00:00Z"
}
```

### `research.error`

Terminal error event emitted inside stream:

```json
{
  "success": false,
  "error": "LLM_UNAVAILABLE",
  "message": "Research temporarily unavailable. Please try again.",
  "status_code": 503,
  "request_id": "uuid",
  "timestamp": "2026-04-07T12:00:00Z"
}
```

Important:

- HTTP status can still be `200` if stream opened successfully.
- Use `research.error.status_code` and `research.error.error` for UX and retries.

## 4. TypeScript Types (frontend)

```ts
export type ResearchSections = {
  eventSummary: string;
  keyVariables: string;
  historicalContext: string;
  currentDrivers: string;
  riskFactors: string;
  dataConfidence: string;
  dataGaps: string;
};

export type ResearchResultData = {
  cached: boolean;
  cachedAt: string | null;
  sections: ResearchSections;
  dataRetrievalAvailable: boolean;
  generatedAt: string;
};

export type ResearchCompletedEvent = {
  success: true;
  data: ResearchResultData;
  request_id: string;
  timestamp: string;
};

export type ResearchErrorEvent = {
  success: false;
  error: string;
  message: string;
  status_code: number;
  request_id: string;
  timestamp: string;
};

export type ResearchProgressEvent = {
  request_id: string;
  stage: string;
  message: string;
  meta?: Record<string, unknown>;
};
```

## 5. React + Vite Implementation Pattern

Use a stream reader + SSE parser.

```ts
// src/lib/researchStream.ts
export async function streamResearch(params: {
  baseUrl: string;
  apiKey: string;
  body: { eventTitle: string; eventSource: string; timestamp: number };
  signal?: AbortSignal;
  onStarted?: (payload: any) => void;
  onProgress?: (payload: any) => void;
  onCompleted?: (payload: any) => void;
  onErrorEvent?: (payload: any) => void;
}) {
  const res = await fetch(`${params.baseUrl}/v1/research`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
      "X-API-Key": params.apiKey,
    },
    body: JSON.stringify(params.body),
    signal: params.signal,
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  if (!res.body) {
    throw new Error("ReadableStream not available");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const handleFrame = (frame: string) => {
    const lines = frame.split("\n");
    let eventName = "message";
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }

    if (!dataLines.length) return;
    const dataText = dataLines.join("\n");
    let payload: any;

    try {
      payload = JSON.parse(dataText);
    } catch {
      return;
    }

    if (eventName === "research.started") params.onStarted?.(payload);
    if (eventName === "research.progress") params.onProgress?.(payload);
    if (eventName === "research.completed") params.onCompleted?.(payload);
    if (eventName === "research.error") params.onErrorEvent?.(payload);
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 2);
      if (frame) handleFrame(frame);
    }
  }
}
```

## 6. UI State Changes

Recommended UI state model:

- `idle`
- `connecting`
- `streaming`
- `completed`
- `error`

Recommended behavior:

- On request start: set `connecting`.
- On `research.started`: set `streaming` and show initial status.
- On each `research.progress`: update a status line/timeline immediately.
- On `research.completed`: render sections and set `completed`.
- On `research.error`: show error message + retry CTA and set `error`.

## 7. Stage Values You Should Expect

Your UI should treat `stage` as a display-only string. Do not hardcode strict workflow assumptions — handle unknown stages gracefully.

Current stages in order:

| Stage | Event type | When |
|-------|-----------|------|
| `request.accepted` | `research.started` | Immediately on request |
| `cache.lookup.started` | `research.progress` | Cache check begins |
| `cache.lookup.hit` | `research.progress` | Result found in cache |
| `cache.lookup.miss` | `research.progress` | Cache miss, fresh pipeline starts |
| `history.write.scheduled` | `research.progress` | Cache hit path only |
| `search.started` | `research.progress` | Web search begins |
| `search.completed` | `research.progress` | Web search done (check `meta.data_retrieval_available`) |
| `llm.started` | `research.progress` | LLM generation begins |
| `llm.completed` | `research.progress` | LLM returned valid sections |
| `llm.unavailable` | `research.progress` | LLM failed — stream ends with `research.error` |
| `persist.started` | `research.progress` | Cache + history write begins |
| `persist.completed` | `research.progress` | Persistence done |

## 8. Abort / Retry

Use `AbortController` to support cancel.

```ts
const controller = new AbortController();

streamResearch({
  baseUrl,
  apiKey,
  body,
  signal: controller.signal,
  onProgress: setProgress,
  onCompleted: setResult,
  onErrorEvent: setError,
});

// cancel button
controller.abort();
```

Retry strategy:

- Retry on transport errors (`fetch` failure, reader failure).
- Retry on `research.error.status_code >= 500`.
- Do not auto-retry on validation/auth failures.

## 9. Migration Checklist

- Replace old JSON `await res.json()` flow for `/v1/research`.
- Add SSE stream parser in frontend data layer.
- Update component state to consume progress events.
- Render final data only from `research.completed`.
- Render stream errors from `research.error`.
- Add cancel support with `AbortController`.
- Keep `X-API-Key` header in requests.

## 10. Quick Local Test (manual)

```bash
curl -N -X POST http://localhost:8000/v1/research \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "eventTitle": "Champions League Final 2025",
    "eventSource": "kalshi.com",
    "timestamp": 1743638400000
  }'
```

You should see multiple `event:` frames, ending in `research.completed` or `research.error`.

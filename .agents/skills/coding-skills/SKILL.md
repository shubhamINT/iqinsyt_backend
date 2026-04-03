---
name: coding-skills
description: Activates a senior software engineer mindset for ALL coding tasks. Use this skill whenever the user asks to write code, build a feature, scaffold a project, refactor existing code, fix a bug, or make any technical decision. Also triggers on phrases like "build me", "create a script", "help me code", or "set up a project".
---

# Senior Software Engineer Skill

You think like a senior engineer. That means one thing above all else:

> **Simple, clean code is always better than complex, clever code.**

---

## Before Writing Any Code

1. **Read first.** Check existing files and understand the project before touching anything.
2. **Check for a `README.md`.** If it exists, read it. If it doesn't, create one.
3. **Plan the simplest solution.** Only add complexity when there's a real reason for it today.

---

## While Writing Code

- Names should explain themselves. No `tmp`, `data2`, or `handleStuff()`.
- One function = one job. If you need "and" to describe it, split it.
- Handle errors explicitly. Never silently ignore them.
- Delete anything that isn't used.
- Provide simple short one line comments to explain the code.
- **Do not output unnecessary code.** Only provide the code that is strictly required for the task.
- **Do not modify indentation or formatting of existing code/files unless absolutely necessary.**

---

## README.md — Always Keep It Current

- **Missing?** Create it with: project description, how to run it, and a simple folder tree.
- **Exists?** Read it before starting. Update the **entire** README to stay parallel with the latest code. This includes updating the folder structure, but you must also check and update any other parts (descriptions, usage instructions, etc.) that might be outdated.

```
project/
├── README.md        # what this is + how to run it
├── src/             # source code
└── tests/           # tests
```

---

## Before Handing Back Any Code

Ask yourself:
- Can I delete anything without breaking it?
- Would a new developer understand this in 5 minutes?
- Does the README still reflect the real structure?

---

## This Project: Indusnet AI Website Backend

> A real-time voice agent built on LiveKit. Know the architecture before touching anything.

### Architecture — Two Separate Processes

| Process | Entry Point | Purpose |
|---------|------------|---------|
| FastAPI API | `src/api/main.py` | Health checks + LiveKit JWT token issuance |
| LiveKit Agent Worker | `src/agents/indusnet/agent.py` | Voice conversations + tool execution |

Run both with `./run_both.sh` or via `docker-compose up`.

### Source Layout — Where Things Go

```
src/
├── agents/indusnet/        # The voice agent (START HERE for agent changes)
│   ├── agent.py            # Agent class, tool registration, LLM/TTS setup
│   ├── prompts.py          # System prompt for the agent
│   ├── state.py            # Conversation state model
│   ├── tools/              # ADD NEW TOOLS HERE (one file per tool)
│   ├── handlers/           # Data handlers (forms, leads, etc.)
│   └── helpers/            # Utilities (filler, vector_search, silence, packet)
├── api/routes/             # ADD NEW API ROUTES HERE
├── services/               # ADD NEW EXTERNAL INTEGRATIONS HERE
│   ├── livekit/            # LiveKit SDK wrappers
│   ├── llm/                # OpenAI LLM/TTS/embedding clients
│   ├── vectordb/           # ChromaDB vector store
│   ├── mail/               # SMTP + calendar invites
│   ├── whatsapp/           # WhatsApp Business API
│   ├── search/             # SearXNG web/image search
│   └── map/googlemap/      # Google Maps distance/routing
└── core/
    ├── config.py           # ALL env vars loaded here — never read .env directly
    └── logger.py           # Shared logger — use this, don't create new loggers
```

### Adding a New Agent Tool

1. Create `src/agents/indusnet/tools/<tool_name>.py`
2. Define the tool function with `@llm.ai_callable()` decorator
3. Register it in `agent.py` where other tools are registered
4. Follow the existing tool files as the pattern — do not invent a new pattern

### Adding a New Service / Integration

- Create `src/services/<category>/<service_name>.py`
- Expose a clean client or function — no business logic in the service layer
- Add any new env vars to `.env` and load them in `src/core/config.py`

### Tech Stack Constraints

- **Python 3.12+** — use modern syntax (match/case, `|` unions, etc.)
- **uv** for dependency management — `uv add <package>`, not pip
- **LiveKit Agents framework** — follow its session/worker lifecycle; do not bypass it
- **OpenAI GPT-4 Realtime** for voice; **GPT-4o-mini** for async tasks (transcription, flashcards, fillers)
- **ChromaDB** for vector search — embeddings use `text-embedding-3-small`
- **Alembic** for DB migrations — run migrations, never alter tables manually

### Critical Things Not to Break

- LiveKit session lifecycle in `src/agents/session.py` — audio pipeline timing is fragile
- ChromaDB collection names and embedding dimensions — changing these breaks the knowledge base
- `.env` variable names — services depend on exact key names loaded in `config.py`
- Docker service names in `docker-compose.yml` — used in inter-container networking

### Environment & Config

- All secrets and feature flags live in `.env`
- Access them **only** via `src/core/config.py` — never `os.getenv()` directly in feature code
- When adding a new integration, add its env var to `.env.example` (or document it)

### Testing

- Tests live in `tests/` — run with `pytest`
- Before adding a new tool or service, check if a test file exists for that area
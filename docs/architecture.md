# Architecture

## Overview

```
Client / automation
        │
        ▼
   FastAPI (/v1)
        │  create run · status · result · cancel
        ▼
  Research service
        │
        ▼
   LangGraph research graph
        │  tools: web search, fetch URL (+ RAG/CRM later)
        ▼
   OpenAI
        │
        ▼
 PostgreSQL
   ├── application tables (runs, reports, sources, events)
   └── LangGraph checkpoint tables
```

## Components

### FastAPI

- Versioned routes under `/v1`.
- Handles auth, validation, run lifecycle endpoints, and health checks.
- Route handlers stay thin; business logic lives in services.

### Research service

- Creates and updates run records.
- Starts the LangGraph job with a stable `run_id` / thread id.
- Enforces timeouts, step budgets, and cancellation where supported.
- Maps graph outcomes to application status (`queued`, `running`, `completed`, `failed`, `cancelled`).

### LangGraph graph

- Fixed multi-node research workflow (see [agent-design.md](agent-design.md)).
- Explicit tool registration and hard caps on tool use.
- PostgreSQL checkpointer for durable state.

### PostgreSQL

- Application schema: runs, reports, sources, events.
- Checkpoint schema: owned by LangGraph’s Postgres checkpointer.
- Application database access uses SQLAlchemy + Alembic with the `psycopg` driver.
- LangGraph checkpoints use the same PostgreSQL database through `psycopg`.

### Observability

- Structured logs: `request_id`, `run_id`, node name, latency, token usage, error codes.
- Metrics/tracing (Prometheus, OpenTelemetry) can follow once the core path is stable.

## Request lifecycle

1. `POST /v1/research/runs` → `202` with `run_id`.
2. Background execution starts the graph (in-process for MVP) with Postgres checkpointer (`thread_id` = `run_id`).
3. Client polls `GET /v1/research/runs/{run_id}`.
4. On `completed`, client loads `GET /v1/research/runs/{run_id}/result`.
5. On `failed` (or after a crash that left checkpoints), client may call `POST /v1/research/runs/{run_id}/resume` to continue from the last checkpoint.

MVP runs jobs in-process (FastAPI background tasks / asyncio). The service interface should allow a later move to a dedicated worker (Arq, Celery, or similar) without rewriting the API.

## Configuration

Environment variables (see `.env.example`):

- `OPENAI_API_KEY`, model names
- `DATABASE_URL`
- `API_KEYS`
- Search provider keys
- `MAX_TOOL_CALLS`, `MAX_GATHER_ITERATIONS`, `MAX_RUN_MINUTES`, `MAX_SEARCH_RESULTS`

## Security baseline

- API key via `X-API-Key` or `Authorization: Bearer`.
- URL fetch tool blocks private IP ranges and enforces size/timeout limits.
- Tool/page content is untrusted input; prompts keep instructions separate from evidence.
- Avoid logging raw prompts, responses, or secrets in production.

## Failure handling

| Failure | Response |
| --- | --- |
| LLM timeout / rate limit | Retry with backoff; fail the run after budget |
| Tool error | Record in state; continue if recoverable, otherwise fail with a clear message |
| Process crash | Resume from last checkpoint when retry is supported |
| Incomplete evidence | Prefer an explicit failure or documented unknowns over fabricated claims |

## Deployment

1. Local: Docker Compose (`api` + `postgres`).
2. Staging/production: same image; managed Postgres; platform secrets.

## Explicit non-goals (v1 architecture)

- Multi-region active-active.
- Streaming chat UI (SSE can be added later without changing the report model).
- Fine-grained RBAC.

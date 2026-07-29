# Roadmap

Delivery milestones for this repository. Each milestone should leave the service in a runnable state.

## M0 — Documentation

- Product brief, architecture, agent design, data model, API, engineering standards, decisions log
- `.env.example`, README, `.gitignore`

## M1 — Application skeleton

- `uv` project with `pyproject.toml` and `src/research_agent`
- FastAPI app exposing `/health` and `/ready`
- Settings via pydantic-settings
- Docker Compose: API + PostgreSQL
- Alembic initialized; first migration for core tables
- Smoke tests for health

Exit criteria: `docker compose up` serves health checks; `uv run pytest` passes.

## M2 — End-to-end research path

- Request/response models aligned with [api.md](api.md)
- `POST /v1/research/runs`, status, and result endpoints
- Minimal LangGraph: normalize → plan → gather → synthesize → finalize
- OpenAI + one web search provider
- Persist runs, sources, and reports in PostgreSQL

Exit criteria: a competitor brief returns cited JSON and Markdown through the API.

## M3 — Durability and controls

- LangGraph Postgres checkpointer
- Budgets (tool calls, iterations, wall-clock timeout)
- `research_events` and richer status progress
- Cancel support (best effort)
- SSRF protections on URL fetch
- Structured logging with `run_id`

Exit criteria: budgets enforced in tests; interrupt/resume path documented.

## M4 — Quality and hardening

- Stronger cite/verify behavior; reject fabricated URLs
- Golden-brief offline eval suite
- Rate limits / concurrency caps
- Accurate OpenAPI and integrator quickstart in README
- Production checklist from [engineering.md](engineering.md)

Exit criteria: eval suite covers critical regressions; checklist signed off for first production deploy.

## M5 — Automation integrations

- Optional completion webhook
- Metadata passthrough for ticket/CRM ids
- Optional internal tools (RAG, CRM) behind feature flags
- Example n8n / Zapier recipe

Exit criteria: an external automation can trigger research and consume results reliably.

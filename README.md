# Research Agent

API service that turns a business research brief into a sourced, structured report. Built for internal automation (ops, strategy, RevOps) on:

| Layer | Stack |
| --- | --- |
| Language | Python 3.12+ |
| Packaging | [uv](https://docs.astral.sh/uv/) |
| Orchestration | LangGraph |
| LLM | OpenAI |
| HTTP API | FastAPI |
| Database | PostgreSQL |

## Capabilities

- Accept a research brief (topic, goals, constraints, audience, depth).
- Plan and execute a bounded research workflow (search → extract → synthesize → cite).
- Return a JSON report plus Markdown, with source URLs.
- Persist runs, sources, and checkpoints for audit and resume.

## Docs

| Document | Description |
| --- | --- |
| [docs/product-brief.md](docs/product-brief.md) | Problem, users, scope, success criteria |
| [docs/architecture.md](docs/architecture.md) | System design and operational boundaries |
| [docs/agent-design.md](docs/agent-design.md) | LangGraph workflow, state, tools, limits |
| [docs/data-model.md](docs/data-model.md) | PostgreSQL schema and report shape |
| [docs/api.md](docs/api.md) | HTTP contracts |
| [docs/roadmap.md](docs/roadmap.md) | Delivery milestones |
| [docs/engineering.md](docs/engineering.md) | Layout, tooling, testing, release checklist |
| [docs/decisions.md](docs/decisions.md) | Architecture / product decisions |

## Local setup

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker.

```bash
cp .env.example .env
uv sync
docker compose up --build
```

- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- Health: `GET /health`
- Readiness (DB): `GET /ready`

### Run API without Docker (DB still via Compose)

```bash
docker compose up postgres -d
uv run alembic upgrade head
uv run uvicorn research_agent.main:app --reload --port 8000
```

### Tests

```bash
uv run pytest
```

## Current milestone

**M1 — Application skeleton** is in place: FastAPI health/ready, Postgres models, Alembic, Compose. Research endpoints and LangGraph arrive in M2.

# Research Agent

API service that turns a business research brief into a sourced, structured report. Built for internal automation (ops, strategy, RevOps) on:

| Layer | Stack |
| --- | --- |
| Language | Python 3.12+ |
| Packaging | [uv](https://docs.astral.sh/uv/) |
| Orchestration | LangGraph |
| LLM | Any OpenAI-compatible provider via `LLM_BASE_URL` (OpenAI, Gemini, Groq, DeepSeek, OpenRouter) |
| Search | Tavily |
| HTTP API | FastAPI |
| Database | PostgreSQL |

## Capabilities

- Accept a research brief (topic, goals, constraints, audience, depth).
- Authenticate `/v1` routes with an API key (`API_KEYS` in `.env` — a shared secret you set).
- Plan searches, gather evidence via Tavily, synthesize a cited report with OpenAI.
- Return structured JSON and Markdown, with source URLs.
- Persist runs, sources, and reports in PostgreSQL.
- Persist LangGraph checkpoints in PostgreSQL (`thread_id` = `run_id`) so interrupted runs can be resumed via `POST /v1/research/runs/{run_id}/resume`.

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
# Set LLM_API_KEY, TAVILY_API_KEY, and API_KEYS (your own shared secret)
uv sync
docker compose up --build
```

- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs — use **Authorize** with the same value as `API_KEYS`
- Health: `GET /health`
- Readiness (DB): `GET /ready`

Day-to-day: `docker compose up` (add `--build` after dependency or Dockerfile changes). `docker compose down` to stop.

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

### Example research request

```bash
curl -X POST http://localhost:8000/v1/research/runs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d "{\"topic\":\"Mid-market CRM competitive landscape\",\"goals\":[\"Top competitors\",\"Pricing signals\"],\"depth\":\"quick\"}"
```

```bash
curl http://localhost:8000/v1/research/runs/RUN_ID -H "X-API-Key: YOUR_API_KEY"
curl http://localhost:8000/v1/research/runs/RUN_ID/result -H "X-API-Key: YOUR_API_KEY"
```

### Research request body

| Field | Required | Description |
| --- | --- | --- |
| `topic` | Yes | Main subject or question to research. Must be at least 8 characters. |
| `goals` | No | Specific questions the report should answer. |
| `constraints` | No | Rules for the research, such as recent sources only or English only. |
| `audience` | No | Intended reader, for example `general`, `strategy`, or `ops`. |
| `depth` | No | Research depth: `quick`, `standard`, or `deep`. |
| `seed_urls` | No | Optional starting URLs. Use `[]` when none are needed. |
| `metadata` | No | Optional tracking data for your own systems. Use `{}` when not needed. |

Example:

```json
{
  "topic": "Mid-market CRM competitive landscape",
  "goals": ["Top competitors", "Pricing signals"],
  "constraints": ["English only"],
  "audience": "strategy",
  "depth": "quick",
  "seed_urls": [],
  "metadata": {}
}
```

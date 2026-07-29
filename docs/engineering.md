# Engineering

## Tooling

| Concern | Choice |
| --- | --- |
| Package / env manager | [uv](https://docs.astral.sh/uv/) |
| Project metadata | `pyproject.toml` |
| Runtime | Python 3.12+ |
| Tests | pytest |
| Migrations | Alembic |
| Containers | Docker Compose |

Common commands (once the skeleton exists):

```bash
uv sync
uv run uvicorn research_agent.main:app --reload
uv run pytest
uv run alembic upgrade head
```

## Repository layout

```
Research-Agent/
├── README.md
├── .env.example
├── docker-compose.yml
├── pyproject.toml
├── alembic/
├── docs/
├── src/
│   └── research_agent/
│       ├── main.py
│       ├── api/
│       ├── core/
│       ├── db/
│       ├── services/
│       ├── agent/
│       └── schemas/
└── tests/
```

## Environment

- Copy `.env.example` to `.env` (gitignored).
- Never commit secrets.
- Local database via Compose.

## Conventions

- Type hints on public functions.
- Pydantic at API and report boundaries.
- Thin route handlers; logic in services and agent nodes.
- Agent loops always take budgets from config.
- Side effects (HTTP, DB) stay explicit and testable.

## Testing

| Layer | Focus |
| --- | --- |
| Unit | Helpers, URL safety, schema validation |
| API | Health, auth rejection, request validation |
| Integration | Graph with mocked LLM/tools |
| E2E | Real provider keys only in protected environments |

## Git

If org rulesets apply: branch `feature/<TICKET>-<description>`, commit `<TICKET> <Imperative summary>`. Confirm the ticket id before the first commit.

## Production checklist

- [ ] Auth on all `/v1` routes
- [ ] `/health` and `/ready`
- [ ] Reproducible migrations
- [ ] Durable checkpoints
- [ ] Budgets and timeouts
- [ ] Structured logs with correlation ids
- [ ] No secrets in repo or logs
- [ ] SSRF / fetch safeguards
- [ ] OpenAPI matches behavior
- [ ] At least one golden eval path
- [ ] Runbook for inspecting and recovering a failed `run_id`

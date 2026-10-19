# Decisions

Record of product and technical decisions for this repo.

| ID | Decision | Status | Notes |
| --- | --- | --- | --- |
| D1 | Web search provider | Accepted | **Tavily**. |
| D2 | API auth (MVP) | Accepted | API key via `X-API-Key` or `Authorization: Bearer`. |
| D3 | Package manager | Accepted | **uv** with `pyproject.toml`. |
| D4 | Report formats | Accepted | Structured JSON and Markdown. |
| D5 | Job execution (MVP) | Accepted | In-process background execution; service boundary allows a later worker. |
| D6 | Git ticket prefix | Open | Required only if org branch/commit rulesets are enforced. |
| D7 | Local stack | Accepted | Docker Compose for API + PostgreSQL. |
| D8 | Python version | Accepted | **3.12+** (pin `.python-version` to 3.12; `uv init` defaulted to 3.14). |
| D9 | LLM provider | Accepted | Any OpenAI-compatible endpoint via `LLM_BASE_URL`; cheap model for plan/verify. |
| D10 | Page reading | Accepted | `fetch_url` with public-IP checks on every redirect hop, 1 MB cap, text/HTML only. |

When a row moves from Open → Accepted, update this table and adjust dependent docs if behavior changed.
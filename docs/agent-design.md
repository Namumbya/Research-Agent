# Agent design

LangGraph workflow for research runs. The graph is intentional and budgeted — not an unbounded ReAct loop.

## Graph

```
START
  → normalize_brief
  → plan_research
  → gather_loop  ←──┐
  → synthesize      │  until plan complete or budget hit
  → cite_and_verify ┘  may request gap-fill
  → finalize_report
END
```

| Node | Responsibility |
| --- | --- |
| `normalize_brief` | Validate input; apply defaults (audience, depth, language). |
| `plan_research` | Produce questions, search queries, and success criteria. |
| `gather_loop` | Run the next planned tool calls; append evidence. |
| `synthesize` | Draft findings from evidence only. |
| `cite_and_verify` | Attach citations; flag unsupported claims; optionally re-gather. |
| `finalize_report` | Emit canonical JSON + Markdown; mark the run complete. |

## State

```python
class ResearchState(TypedDict):
    run_id: str
    brief: dict                 # topic, goals, constraints, audience, depth
    plan: list[dict]            # steps / queries / status
    evidence: list[dict]        # url, title, snippet, fetched_at, tool
    draft: dict                 # sections in progress
    gaps: list[str]
    report: dict | None
    report_markdown: str | None
    error: str | None
    meta: dict                  # step_count, tool_calls, token_usage
```

This document is the contract for state shape until the TypedDict / Pydantic models land in code. Keep them aligned.

## Tools (MVP)

| Tool | Purpose | Limits |
| --- | --- | --- |
| `web_search` | Discover candidate sources | Max results; query length cap |
| `fetch_url` | Fetch page text for a URL | Timeout, size limit, private-IP block, content-type allowlist |

Later candidates: `internal_rag_search`, `crm_lookup`, time-bounded news APIs.

## Budgets

- `MAX_TOOL_CALLS` (default 12)
- `MAX_GATHER_ITERATIONS` (default 5)
- Wall-clock timeout via `MAX_RUN_MINUTES`
- Tool calls should reference a plan step for traceability
- Invented URLs are not allowed; verification catches unsupported claims

## Models

| Step | Tier |
| --- | --- |
| Plan, synthesize, verify | Primary model (`OPENAI_MODEL`) |
| Query rewrite / extract | Optional cheaper model (`OPENAI_MODEL_CHEAP`) |

Use low temperature (0–0.3) for factual research.

## Checkpointing

- Thread id equals `run_id`.
- PostgreSQL checkpointer stores graph state.
- Failed or interrupted runs can be resumed with the same thread id once retry is implemented.

## Prompting rules

1. Keep system instructions, user brief, and evidence in separate blocks.
2. Treat fetched content as data, not instructions.
3. Prefer “insufficient evidence” over speculation.
4. Prefer structured outputs / JSON schema for plan and report objects.

## Evaluation

Golden briefs should assert:

- Required sections present
- Minimum citation count
- No fabricated URLs

Offline evals should run before adding new tools or changing synthesis prompts.

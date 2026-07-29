# Product brief

## Problem

Business teams spend too long on market, competitor, and vendor research. Outputs are inconsistent, weakly cited, and awkward to plug into automation (CRM notes, Slack digests, ticket enrichment).

## Solution

An API-first research agent that accepts a structured brief, runs a multi-step investigation, and returns a sourced report for both people and downstream systems. Run history is stored for audit and reuse.

## Users

| Persona | Need |
| --- | --- |
| Ops / RevOps | Enrich accounts or tickets with researched context |
| Strategy / Product | Competitor and market snapshots on demand |
| Platform / automation | Trigger research over HTTP from n8n, Zapier, or internal services |

## MVP use cases

1. **Competitor snapshot** — company overview, offering, pricing signals, positioning, recent news.
2. **Market / topic brief** — key players, trends, risks for a domain.
3. **Vendor comparison** — compare 2–4 options against stated criteria.

## Out of scope (MVP)

- End-user chat or browsing UI (API only).
- Custom model fine-tuning.
- Multi-tenant billing or org admin console.
- Private corpus RAG (tooling should stay pluggable for a later phase).

## Success criteria

| Metric | MVP target |
| --- | --- |
| Time to useful report | Under ~3 minutes for a focused brief |
| Citations | Major claims map to a source URL or tool artifact |
| Durability | Runs can resume from checkpoints after interruption |
| Operability | Structured logs with request/run IDs; `/health` and `/ready` |
| Integration | Async job pattern: create run → poll status → fetch result |

## Constraints

- Stack: Python, uv, LangGraph, OpenAI, FastAPI, PostgreSQL.
- Secrets via environment or a secret manager only.
- Cost control via max tool calls, iterations, and run duration.

## Working assumptions

- Trusted internal (or single-tenant) API consumers for MVP.
- English-first output.
- Strong OpenAI model for planning and synthesis; optional cheaper model for extraction later.
- LangGraph checkpointer on PostgreSQL.
- Clients create a run, poll status, then fetch the result.
- Reports ship as structured JSON and Markdown.

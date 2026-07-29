# Data model

## Principles

- Application tables own product meaning (brief, status, final report).
- LangGraph owns execution checkpoints; do not mirror every node blob into app tables unless a product feature needs it.
- Public identifiers are UUIDs.
- Timestamps are UTC (`timestamptz`).

## Tables

### `research_runs`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` PK | Public `run_id` |
| `status` | `text` | `queued` \| `running` \| `completed` \| `failed` \| `cancelled` |
| `brief` | `jsonb` | Normalized brief |
| `plan` | `jsonb` nullable | Optional latest plan snapshot |
| `error_message` | `text` nullable | Safe client-facing error |
| `model_config` | `jsonb` | Models and limits used for the run |
| `started_at` | `timestamptz` nullable | |
| `finished_at` | `timestamptz` nullable | |
| `created_at` | `timestamptz` | |
| `updated_at` | `timestamptz` | |
| `created_by` | `text` nullable | API key id or calling service |

Indexes: `(status, created_at DESC)`, `(created_at DESC)`.

### `research_reports`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` PK | |
| `run_id` | `uuid` FK → `research_runs`, UNIQUE | One final report per run |
| `report_json` | `jsonb` | Canonical structured report |
| `report_markdown` | `text` | Human-readable form |
| `created_at` | `timestamptz` | |

### `research_sources`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` PK | |
| `run_id` | `uuid` FK | |
| `url` | `text` | |
| `title` | `text` nullable | |
| `snippet` | `text` nullable | |
| `raw_ref` | `jsonb` nullable | Tool metadata |
| `created_at` | `timestamptz` | |

Index: `(run_id)`. Optional unique: `(run_id, url)`.

### `research_events`

Append-only progress and audit stream.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `bigserial` PK | |
| `run_id` | `uuid` FK | |
| `level` | `text` | `info` \| `warn` \| `error` |
| `event_type` | `text` | e.g. `node_started`, `tool_called` |
| `payload` | `jsonb` | |
| `created_at` | `timestamptz` | |

## LangGraph checkpoints

Created and owned by LangGraph’s Postgres checkpointer. Do not edit those tables by hand.

## Canonical report JSON

```json
{
  "title": "string",
  "executive_summary": "string",
  "sections": [
    {
      "heading": "string",
      "content": "string",
      "citations": [{"source_id": "uuid", "url": "string"}]
    }
  ],
  "key_findings": ["string"],
  "risks_or_unknowns": ["string"],
  "follow_up_questions": ["string"],
  "sources": [
    {"id": "uuid", "url": "string", "title": "string"}
  ]
}
```

## Retention

Local/MVP: retain indefinitely. Production retention (for example 90 days) and purge jobs are a later ops concern.

## Migrations

Schema changes go through Alembic. No manual production DDL.

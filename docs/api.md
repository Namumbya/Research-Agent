# API

Base path: `/v1`  
Content-Type: `application/json`  
Auth: `X-API-Key: <key>` or `Authorization: Bearer <key>`

## Health

### `GET /health`

```json
{ "status": "ok" }
```

### `GET /ready`

Verifies database connectivity.

```json
{ "status": "ready", "database": "ok" }
```

## Create research run

### `POST /v1/research/runs`

Request:

```json
{
  "topic": "Acme Corp competitive landscape in mid-market CRM",
  "goals": [
    "Identify top 5 competitors",
    "Compare pricing signals and positioning"
  ],
  "constraints": [
    "Prefer sources from the last 18 months",
    "English only"
  ],
  "audience": "strategy",
  "depth": "standard",
  "seed_urls": [],
  "metadata": {
    "ticket_id": "optional-external-id"
  }
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `topic` | yes | 8–500 characters |
| `goals` | no | List of strings |
| `constraints` | no | List of strings |
| `audience` | no | e.g. `ops`, `strategy`, `general` |
| `depth` | no | `quick` \| `standard` \| `deep` (maps to budgets) |
| `seed_urls` | no | Optional starting URLs |
| `metadata` | no | Opaque client metadata |

Response `202 Accepted`:

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2026-07-29T20:00:00Z"
}
```

## Get run status

### `GET /v1/research/runs/{run_id}`

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "created_at": "2026-07-29T20:00:00Z",
  "started_at": "2026-07-29T20:00:01Z",
  "finished_at": null,
  "error_message": null,
  "progress": {
    "current_node": "gather_loop",
    "tool_calls": 3,
    "evidence_count": 5
  }
}
```

`progress` may be partial until event streaming is fully wired.

## Get run result

### `GET /v1/research/runs/{run_id}/result`

`200` when status is `completed`:

```json
{
  "run_id": "...",
  "status": "completed",
  "report": {},
  "report_markdown": "# Title\n\n...",
  "sources": [
    {"id": "...", "url": "https://...", "title": "..."}
  ]
}
```

- `409` if the run is not completed yet
- `404` if the run does not exist
- Failed runs: use the status endpoint (`error_message`); do not return a fake success body here

## Cancel run

### `POST /v1/research/runs/{run_id}/cancel`

```json
{ "run_id": "...", "status": "cancelled" }
```

Best-effort cancellation; available once durability and orchestration support it.

## Errors

```json
{
  "error": {
    "code": "validation_error",
    "message": "topic is required",
    "details": {}
  }
}
```

## Versioning

Breaking changes go to `/v2`. Additive fields on `/v1` are allowed when backward compatible.

## Client flow

1. Create a run.
2. Poll status every 2–5 seconds (back off after ~30s).
3. Fetch the result when status is `completed`.
4. On `failed`, read `error_message` before deciding whether to retry.

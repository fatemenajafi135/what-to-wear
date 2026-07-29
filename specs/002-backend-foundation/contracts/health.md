# Contract: `GET /health`

The only HTTP surface this slice exposes. Infrastructure-facing (contributors, and later,
deployment tooling) — not a product endpoint.

## Request

```
GET /health
```

No parameters, no auth, no body.

## Responses

### 200 — database reachable

```json
{
  "status": "ok"
}
```

### 503 — one or more dependencies unreachable

```json
{
  "status": "unhealthy",
  "failed_dependencies": ["database"]
}
```

`failed_dependencies` names each dependency that failed its check. This slice checks exactly
one: `"database"` (a `SELECT 1` against the engine from `core/db.py`). The list shape is
kept plural/extensible on purpose — later slices (e.g. a vector store, a cache) add their own
name to the same list rather than inventing a second response shape, mirroring the legacy
`/health` route's precedent.

## Behavioral guarantees

- Never raises an unhandled exception. A database connection failure is caught and reported
  as `"unhealthy"` with `503`, not a `500` or a crash (spec Edge Cases).
- Does not require any request-scoped state (no auth header, no session) — this route exists
  precisely so it can be probed by something that isn't a signed-in user.
- The database check opens and closes a connection per call; it does not hold one open
  between health checks.

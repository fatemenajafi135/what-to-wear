# Contract: `GET /api/v1/whoami`

The protected example route required by the handoff (§5.3) — not a product endpoint. It
exists to prove `get_current_user_id` rejects a missing/invalid/expired token and accepts a
valid one, end to end through a real FastAPI route, not just via the dependency's own unit
tests.

## Request

```
GET /api/v1/whoami
Authorization: Bearer <supabase-access-token>
```

No body, no query parameters. The `Authorization` header is required.

## Responses

### 200 — token verified

```json
{
  "user_id": "9c2c6b1e-....-....-....-............"
}
```

`user_id` is the JWT's `sub` claim, returned verbatim as a string — this route does not look
it up against any local table (there isn't one).

### 401 — missing, malformed, invalid-signature, or expired token

```json
{
  "detail": "Missing bearer token"
}
```

or

```json
{
  "detail": "Invalid token: <underlying pyjwt error>"
}
```

All four failure modes (missing / malformed / bad signature / expired) return the same
status code and the same response shape — the caller cannot distinguish "no token" from
"bad token" from the response alone, which is the point (FR-015: an equivalent unauthorized
failure in every case, not a signal an attacker could use to distinguish reasons).

## Behavioral guarantees

- Signature verification happens against the Supabase project's JWKS endpoint
  (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`), not against a value trusted from the
  request itself.
- No database access — this route only depends on `get_current_user_id`, per the handoff's
  instruction that this is "proof the dependency works end to end," not a product feature.
- Response model is a Pydantic model (`WhoamiResponse`), consumed on the frontend (if at
  all, since nothing in this feature's scope calls it from the UI) only through
  OpenAPI-generated types, per Constitution VII — no hand-written duplicate type.

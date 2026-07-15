# Phase 0 Research: Closet Persistence

No `NEEDS CLARIFICATION` markers remained in Technical Context — this
research resolves implementation-approach decisions, not open unknowns.

## Qdrant scope

- **Decision**: No Qdrant collection for wardrobe/closet items in this
  feature. Qdrant (cloud-hosted) continues to hold only the style-KB
  collection, untouched.
- **Rationale**: confirmed with the project owner. Today, wardrobe items are
  a flat in-memory list formatted as text for the LLM — there's no existing
  Qdrant collection for them to begin with. Per-slot vector-ranked candidate
  retrieval belongs to Feature 002 (styling-agent), which explicitly designs
  the combinatorial engine and hard-filter pruning. Introducing it here would
  both violate spec FR-012 ("no change to retrieval behaviour") and duplicate
  design work Feature 002 already owns.
- **Alternatives considered**: building the Postgres-hard-filter +
  Qdrant-dense-ranking hybrid now (per the older `build_plan.md` Phase 2.2).
  Rejected — bigger scope than this feature's spec calls for, and premature
  relative to Feature 002's design.

## User identity — no local `users` table

- **Decision**: `wardrobe_items.user_id` is a plain UUID column populated from
  the verified JWT's `sub` claim. No local `users` table is created in this
  feature.
- **Rationale**: Supabase auth already owns the canonical user record
  (`auth.users`). Mirroring it locally adds a sync-maintenance burden with no
  consumer in this feature — the constitution's simplicity gate disallows
  introducing structure ahead of an actual second use. If a future feature
  needs to join against user profile data, that's the point to add it.
- **Alternatives considered**: a local `users` shadow table populated on
  first login. Rejected for now as unused scope; can be added later without
  disrupting `wardrobe_items` (its `user_id` column doesn't need to change).

## JWT verification approach

Context: the Supabase project has **both** kinds of signing key available — a
new asymmetric **ES256 (ECC P-256)** signing key, and the **legacy HS256
shared secret**. This decides how `auth.py` verifies tokens.

- **Decision**: verify the JWT signature locally with `pyjwt[crypto]` using
  **ES256 via the project's JWKS endpoint**
  (`https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`), with
  `pyjwt`'s `PyJWKClient` (which fetches and caches the public keys), checking
  `audience="authenticated"`, and extracting `sub` as `user_id`. The
  `config.py`-style env layer holds the project ref / JWKS URL; no secret is
  stored in the backend.
- **Rationale**: asymmetric verification is Supabase's current recommended
  path and is strictly safer — the backend holds only the **public** key, so
  a backend compromise cannot mint tokens (an HS256 shared secret can both
  sign and verify, so leaking it lets an attacker forge user tokens). It also
  survives key rotation automatically via JWKS. Corrects the plan input's
  imprecise "using the service key": the service_role key is itself a
  long-lived admin JWT for privileged access, **not** the key used to verify a
  user's token — user-token verification uses the signing key's public half.
- **Precondition to confirm at implementation**: ES256 must be the project's
  **active/current** signing key (so newly issued user tokens are ES256). If
  the legacy HS256 key is still current and tokens come out HS256, either
  promote the ES256 key to current in the Supabase dashboard (recommended), or
  fall back to the HS256 path below.
- **Fallback (HS256)**: if staying on the legacy key, verify with the shared
  **JWT secret** (not the service_role key) and `algorithms=["HS256"]`. Same
  `sub`/`audience` handling; simpler but less secure. Kept as an option, not
  the default.
- **Alternatives considered**: calling Supabase's `auth.get_user()` admin API
  per request. Rejected — adds latency and an external-service dependency to
  every wardrobe request for no benefit over local signature verification.

## `fabric` field and catalog seed data

- **Decision**: `fabric` is added as a new, **nullable** column/field (both in
  Postgres and in `schema.py`'s `WardrobeItem`). The one-time catalog seed
  from `data/fixtures/wardrobe.json` leaves `fabric` unset for all 40 existing
  items.
- **Rationale**: the fixture has zero `fabric` values today (verified: 40
  items, 0 occurrences of `"fabric"` in the file). Requiring it `NOT NULL`
  would make the seed step fail outright. Nullable-with-correction matches
  the project's own stated posture toward this field elsewhere ("the VLM will
  get fabric wrong and that's fine — PATCH lets the user correct it").
- **Follow-up flagged, not blocking**: catalog items will show a blank
  fabric until someone backfills it (manually, or via Feature 003's future
  VLM extraction). Worth a follow-up task, not a blocker for this feature.
- **Alternatives considered**: a placeholder default like `"unknown"`.
  Rejected — indistinguishable from a real fabric named "unknown" later;
  `NULL` is the honest "not yet known" signal.

## `source` (catalog vs. upload) field

- **Decision (revised)**: add `wardrobe_items.source` now (`catalog` | `upload`,
  default `'catalog'`). Reversed from an earlier draft of this document that
  deferred it to Feature 003.
- **Clarification on what actually consumes it**: this column records how an
  *owned* item entered the closet — that's a Feature 003 (photo upload)
  concern. It is **not** what Feature 002's similar-item substitution needs:
  substitution can tell "you don't own this" structurally, from whether a
  suggested item's id came from `catalog_items` or `wardrobe_items`, without
  reading a `source` field at all. So this column sits unused past its
  default until Feature 003 lands.
- **Rationale for adding it anyway, now**: it's a single cheap, low-risk
  column, it matches the original build-plan schema, and it avoids a schema
  migration when Feature 003 (two features away, not a distant hypothetical)
  needs to distinguish upload-sourced items. The cost of carrying an
  unused-but-defaulted column for one feature cycle is lower than the cost of
  a later migration plus backfill.
- **Alternatives considered**: leaving it out until Feature 003 (original
  decision in this document). Reasonable on pure YAGNI grounds, but rejected
  on a cost/benefit basis given how close Feature 003 is and how cheap the
  column is to add today.

## Similar-item substitution (Feature 002) and catalog embeddings

- **Decision**: catalog items do **not** need vector embeddings for
  substitution. Substitution ranks `catalog_items` candidates for a missing
  required slot using the same deterministic attribute-distance scoring the
  styling engine already needs for real closet items — formality distance,
  warmth distance, season overlap, color harmony — not a nearest-neighbor
  embedding search.
- **Rationale**: this is a structured/tabular similarity problem (formality,
  warmth, season, color are all already explicit columns), not a semantic one
  that needs dense embeddings. It also keeps substitution consistent with
  constitution Principle II (deterministic core, LLM at the edges) instead of
  introducing a second, embedding-based similarity mechanism alongside the
  deterministic scorer Feature 002 is already building. It also means neither
  `wardrobe_items` nor `catalog_items` need an embedding column or a Qdrant
  collection in this feature or the next one.
- **Alternatives considered**: embedding `catalog_items` and doing a Qdrant
  nearest-neighbor search for substitution. Not rejected outright — flagged
  as a possible future upgrade if attribute-distance substitution turns out
  too coarse (e.g. it can't capture aesthetic/silhouette similarity) — but
  not adopted now, since it would add an embedding pipeline and a new Qdrant
  collection for a case the deterministic scorer may already handle well
  enough. This decision belongs to Feature 002's own plan, not this feature's
  data model; recorded here because Feature 001 is where "does the catalog
  need an embedding column" gets decided (it doesn't, not yet).

## Storage shapes for `colors` and `season`

- **Decision**: both stored as Postgres `JSONB` (list of strings), mirroring
  the existing Pydantic `list[str]` shape exactly. `formality` and `fabric`
  are plain `VARCHAR`; `warmth` is `INTEGER` with a `CHECK (warmth BETWEEN 0
  AND 5)` constraint.
- **Rationale**: simplest mapping from the existing Pydantic model, avoids
  Postgres native array/enum migration friction, and keeps validation
  (hex format, controlled vocabularies) at the Pydantic boundary where it
  already lives in `colors.py`/`schema.py`, rather than duplicating it as DB
  constraints.
- **Alternatives considered**: Postgres native `ENUM` types for
  `formality`/`season`, and native `TEXT[]` arrays for `colors`/`season`.
  Rejected — more Alembic migration ceremony for no behavioral gain in a
  solo-scale project.

## Field naming: `season` not `seasons`

- **Decision**: keep the existing Pydantic field name `season` (even though
  it holds a list and the spec prose says "seasons").
- **Rationale**: constitution Principle VI freezes the existing schema;
  renaming an existing field is exactly the kind of breaking rename the
  constitution says requires explicit justification, and there's no
  functional reason to rename here.

## Terminology: "wardrobe" in code, "closet" as UI label

- **Decision**: all code, API routes, database tables, and ORM/function
  identifiers use **wardrobe** (`wardrobe_items`, `/wardrobe/items`,
  `list_wardrobe_items`, `WardrobeItemRow`). **Closet** is reserved as a
  user-facing display word only — the frontend may say "your closet," but no
  `closet_*` identifier exists in code. The spec (a product document) keeps
  "closet" as the product term; every technical artifact uses "wardrobe."
- **Rationale**: the existing pipeline already uses `WardrobeItem` as its
  frozen Pydantic contract (Principles VI/VII), so "wardrobe" is the anchor
  term that cannot move. Standardizing new code on it means zero naming drift;
  standardizing on "closet" instead would require renaming the frozen contract
  across the authoritative pipeline (schema, context_assembler, generator,
  eval, retrieval, memory) and tripping the Principle I no-regression gate —
  high churn for a cosmetic change. Display copy in the UI is independent of
  code identifiers, so "closet" survives as the product word at no cost.
- **ORM naming**: the SQLAlchemy row classes are `WardrobeItemRow` /
  `CatalogItemRow`, suffixed `Row` so they don't shadow the frozen Pydantic
  `WardrobeItem` when both are imported in `crud.py`.
- **Applies to future features**: 002-005 follow the same rule — wardrobe in
  code, closet only as UI copy.

## Supabase transaction pooler + SQLAlchemy/psycopg (operational gotcha)

- **Context**: the plan uses the Supabase **transaction pooler on port 6543**
  (Supavisor). Transaction-mode pooling does not support session-level state
  or server-side prepared statements, which psycopg3/SQLAlchemy use by
  default — this surfaces as confusing "prepared statement already exists" /
  "does not exist" errors under load if left unaddressed.
- **Decision / note for T003 + T005**:
  - App engine (T003): disable prepared statements for the pooled connection
    (psycopg3: `prepare_threshold=None`) and don't rely on a long-lived
    server-side session; a `NullPool` or short-lived connections play best
    with an external pooler.
  - Alembic migrations (T005): DDL over the transaction pooler is generally
    fine, but if `alembic upgrade`/autogenerate misbehaves, run migrations
    against the **direct** connection (port 5432) and keep 6543 for the app.
    Keep both URLs available in `.env`.
- **Rationale**: this is a well-known Supabase-pooler footgun; flagging it now
  saves the debugging loop the build plan warns about. Not a design change —
  just connection configuration T003/T005 must get right.

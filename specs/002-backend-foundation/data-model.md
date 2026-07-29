# Data model: Backend and database foundation

This slice creates no product table. What follows are the foundation-level database objects
`0001_init.sql` defines — the vocabulary every later migration builds on — plus the one
application-level model this slice's own code needs.

## Database objects (`infra/supabase/migrations/0001_init.sql`)

### Extensions

| Extension | Why |
|---|---|
| `pgcrypto` | `gen_random_uuid()` for every future table's primary-key default. See research.md §6. |

### Enums (the frozen taxonomy, Constitution Principle VI)

**`category_group`** — the six slot groups every wardrobe item belongs to:

```
'top' | 'bottom' | 'full_body' | 'outerwear' | 'footwear' | 'accessory'
```

**`formality_level`** — the six-value formality scale:

```
'casual' | 'smart_casual' | 'business_casual' | 'semi_formal' | 'formal' | 'black_tie'
```

Both are Postgres `CREATE TYPE ... AS ENUM (...)`. Per Principle VI, features MUST conform
to these values and MUST NOT introduce a parallel numeric scale or rename a group — any
change is a breaking, explicit migration, not an addition to this one.

### Trigger function: `public.set_updated_at()`

A `plpgsql` trigger function, `NEW.updated_at := now(); RETURN NEW;`. No table uses it yet.
Every future table with an `updated_at` column attaches it via:

```sql
CREATE TRIGGER trg_<table>_updated_at
  BEFORE UPDATE ON <table>
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
```

### Row-level-security convention (documented, not yet applied)

Written as a SQL comment block in the migration, not executable SQL — there is no table to
attach a policy to yet (research.md §7). The convention every table from feature 004 onward
follows:

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table>_select_own" ON <table>
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "<table>_modify_own" ON <table>
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
```

Every per-user table carries a `user_id uuid` column (no local `users` table — `user_id` is
the opaque `sub` claim from the verified Supabase JWT, per legacy precedent). The mechanism
that populates `auth.uid()` for a request made through the backend's own database connection
is feature 003's (Auth) responsibility, not this slice's.

## Application-level model (`backend/src/whattowear/core/config.py`)

**`Settings`** (pydantic-settings `BaseSettings`, loaded lazily via `get_settings()` — never
instantiated at import time):

| Field | Type | Default | Source |
|---|---|---|---|
| `database_url` | `str` | *(required when read)* | `DATABASE_URL` |
| `log_level` | `str` | `"INFO"` | `LOG_LEVEL` |
| `environment` | `str` | `"development"` | `ENVIRONMENT` |

No other entity exists in this slice's own code. `GET /health`'s response is a plain dict,
not a persisted or reusable schema, and is specified in `contracts/health.md` rather than
here.

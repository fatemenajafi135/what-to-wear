# Fix brief — Feature 002 review findings

**From:** tech lead · **Follows:** `docs/handoffs/002-backend-foundation.md` · **Scope:**
small, three items · **Branch:** cut from `rebuild` (002 is merged)

Feature 002 was reviewed and merged. The implementation is correct — including the thing
the slice exists for. These are three defects found around it, none of which block anything.

---

## 1. The import-safety guard does not guard anything

**This is the important one.** The whole premise of this slice is trap 1: the package must
import with no environment at all. The implementation achieves it — verified module by
module with `env -i`, all of `whattowear`, `core.config`, `core.db`, `core.logging` and
`main` import cleanly with zero environment variables.

But the *guard* is hollow. Both `tests/unit/test_import_safety.py` and the CI step run:

```
import whattowear
```

and `backend/src/whattowear/__init__.py` is **0 bytes**. Proof:

```
$ env -i .venv/bin/python -c "import whattowear, sys; \
    print([m for m in sys.modules if 'whattowear' in m])"
['whattowear']
```

One module. The submodules are never loaded, so nothing about `config.py`, `db.py` or
`main.py` is exercised. If someone later adds a module-level `get_settings()` or
`create_engine()` to any of them — exactly the legacy defect — this test and this CI step
both still pass.

**Fix:** import the modules that can actually regress. Parametrise over
`whattowear.core.config`, `whattowear.core.db`, `whattowear.core.logging` and
`whattowear.main`, each in its own `env={}` subprocess. `main` matters most: it transitively
pulls in both config and db, so it is the one that would catch a real regression.

Apply the same change to the CI step, which has the identical hole.

## 2. Committed code is not formatted, and CI cannot tell

`uv run ruff format --check .` fails: `backend/src/whattowear/core/logging.py` would be
reformatted (line 30, a long dict comprehension).

`.pre-commit-config.yaml` **does** run `ruff-format`, so this only reaches the repository if
pre-commit was never installed. CI runs `ruff check` but **not** `ruff format --check`, so it
cannot catch the drift either. Local and CI currently disagree about what "clean" means, and
CI is the weaker of the two.

**Fix:** run `uv run ruff format .`, and add a `ruff format --check` step to the backend CI
job next to the existing lint step. Then `pre-commit install` locally so the hook actually
runs.

## 3. The health endpoint's failure path is untested

`test_health.py` covers the 200 case. `main.py` also has a 503 branch —
`_database_reachable()` returning false yields `{"status": "unhealthy",
"failed_dependencies": ["database"]}`. That branch is the entire reason the endpoint reports
dependency state rather than just returning 200, and nothing exercises it.

**Fix:** one test that forces the failure, monkeypatching `_database_reachable` or pointing
the engine at an unreachable URL, asserting 503 and the body shape in `contracts/health.md`.

---

## Definition of done

- [ ] The import guard imports `whattowear.main` and the three `core` modules, each with
      `env={}`, in both the test and CI.
- [ ] **Verify the guard actually fails** when it should: temporarily add a module-level
      `get_settings()` to `main.py`, confirm the test goes red, then revert. A regression
      test that has never been seen to fail is not yet a regression test.
- [ ] `uv run ruff format --check .` passes.
- [ ] CI runs `ruff format --check` on the backend.
- [ ] A test covers the 503 branch of `GET /health`.
- [ ] `ruff check`, `ruff format --check`, `mypy`, `pytest` and `lint-imports` all clean.

---

## For the record — what was verified and held up

Reviewed independently rather than taken from the report:

- **All five modules import with a completely empty environment.** The legacy import-time
  engine defect is genuinely not reproduced. `get_engine()` and `get_settings()` are both
  `lru_cache`-wrapped, and `main.py` builds the engine in `lifespan`, not at module scope —
  with the distinction between import-time and app-run-time laziness reasoned about
  explicitly in the docstring.
- **The pooler knowledge carried forward correctly**, with attribution: `prepare_threshold=None`,
  `NullPool`, and the psycopg3 scheme rewrite. The local pooler tenant discovery
  (`postgres.pooler-dev`, port 54329, not the direct 54322) is a genuinely useful finding
  that was documented rather than left in someone's shell history.
- `ruff check`, `mypy`, `pytest` and `lint-imports` all pass.
- The migration is correctly scoped: extension, the two Principle VI enums matching the
  frozen taxonomy exactly, an `updated_at` trigger function, **zero product tables**.
- The import-linter contract is narrow, passes, and explains in a comment why it is narrow
  and what feature 007 must extend.
- No `ports.py`, no Alembic, no product endpoints, no cloud Supabase link, no secrets.
- CI covers both stacks, and every frontend script it invokes exists.

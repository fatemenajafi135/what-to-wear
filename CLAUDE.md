# What to Wear — rebuild

A from-scratch rebuild of the fashion/wardrobe PWA. `rebuild` is an orphan branch and
shares no history with `main`. Spec Kit will extend this file in Phase 4.

## Ground rules

- `main` stays live and untouched. Never rebase or force-push it.
- `rebuild` is an orphan branch with no shared history with `main`. It becomes `main` at cutover.
- One Next.js codebase serves the desktop web experience **and** the installed mobile PWA.
  Routes are identical across form factors; only the chrome changes. There is no second app.
- `design/design-system.md`, plus `docs/design-decisions.md` where it is silent or
  self-contradictory, are the only sources of visual truth. Nothing visual is invented in code.

## Design handoff

- `design/design-system.md` — the contract: tokens, components, states, copy. The single
  source of truth for every visual value. Do not invent colours, spacing, type or motion.
- `design/known-gaps.md` — what the design deliberately leaves to be decided in code.
- `docs/design-decisions.md` — resolutions for what the design system leaves incomplete or
  contradicts itself on, and the form-control spec it never contains. Fills gaps only;
  never overrides a value the design system states clearly.
- `design/prototype/` — **reference only.** Static throwaway mockups from Claude Design.
  Read them to understand intent. **Never copy code out of this directory.**
- `design/prototype/_scaffolding/` — prototype plumbing (`ios-frame.jsx`, `support.js`).
  Never port. It must not appear anywhere in the product.

## Repositories and directories

- `../app-legacy` — a git worktree of the live prototype (`main` branch). **Read-only.**
  Read it to understand the old AI code. Never modify, move or delete anything in it.
- `frontend/` — Next.js App Router + TypeScript.
- `backend/` — FastAPI + `uv`. Internal layout is **not settled** — it is decided in the
  Phase 4 constitution. Do not assume a structure before then.
- `docs/` — durable project documentation.
- `notes/` — local-only scratch. Never staged, committed, or referenced from tracked files.

## Conventions

- Conventional Commits (`docs(design):`, `chore(ai):`, `feat(001):` …).
- No secrets in the repo. Commit only `.env.example`.

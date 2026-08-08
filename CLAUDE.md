# What to Wear

The from-scratch rebuild of the fashion/wardrobe PWA. **Cutover is done** (2026-08-08):
`main` is the rebuild and is the default branch. Work happens here.

## Ground rules

- `main` is the trunk and is deployed. Never rebase or force-push it.
- The prototype this replaced is preserved at the `prototype-final` tag and on the
  `legacy-main` branch. Neither is deployed; nothing builds from them.
- **`main`'s history contains the prototype's 155 commits as an unrelated second parent**
  (merge `41c593b`, `-s ours` — it changed no files). The rebuild was developed as an
  orphan branch, and that history was grafted on at cutover so GitHub would keep
  attributing the prototype's commits. Practical consequence: `git bisect` on the trunk
  can wander into a codebase that shares nothing with this one. Bound it —
  `git bisect start HEAD <a-rebuild-era-commit>`.
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

- `../app-legacy` — **no longer present.** It was a read-only worktree of the prototype,
  removed at cutover. The code is not lost: `git worktree add ../app-legacy legacy-main`
  recreates it from the `legacy-main` branch (or the `prototype-final` tag) if a question
  about the old AI code comes up. If you recreate it, it stays read-only.
- `frontend/` — Next.js App Router + TypeScript.
- `backend/` — FastAPI + `uv`. Internal layout is **not settled** — it is decided in the
  Phase 4 constitution. Do not assume a structure before then.
- `docs/` — durable project documentation. `docs/deferred-work.md` is the register of
  decided-but-parked work; a slice that defers something adds a row there.
- `notes/` — local-only scratch. Never staged, committed, or referenced from tracked files.

## Conventions

- Conventional Commits (`docs(design):`, `chore(ai):`, `feat(001):` …).
- No secrets in the repo. Commit only `.env.example`.

## Branches

Spec Kit creates `###-slug`. **Rename it immediately** — the repo also holds the old
prototype's branches, which share the same numbers (`003-mvp-app` is *legacy*, not this
rebuild), so an unprefixed number is ambiguous:

```bash
git branch -m feat/003-auth      # right after /speckit-specify cuts 003-auth
```

| Kind | Format |
|---|---|
| Feature | `feat/###-slug` |
| Follow-up fix | `fix/###-slug` |
| Docs only | `docs/slug` |

The spec directory keeps Spec Kit's own name (`specs/003-auth/`) — only the branch is
prefixed. Renaming is safe: Spec Kit resolves the feature directory from
`.specify/feature.json`, never by parsing the branch name.

- **Code** — feature and fix work — branches off `main` and merges back by PR. This holds
  during incidents too. Several 017 fixes went straight to the trunk mid-deploy because
  each felt urgent; "we're mid-incident" is when landing unreviewed code on a deploying
  branch matters *most*, not least.
- **Docs-only changes** may be committed straight to `main`; a branch and a PR for a
  markdown file is ceremony without benefit.
- Unnumbered infra/config work that fits no feature uses `chore/slug`.
- **Never `git push` from an agent session.** The human pushes. Local `pull.rebase true` is
  what keeps history linear when they pull after a PR merge — without it, unpushed commits
  on `main` produce duplicate merge commits.
- Never rename or delete any branch you did not create.

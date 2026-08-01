# Handoff — Feature 008: Styling chat

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/008-styling-chat`, cut
from `rebuild` · **Migration number: `0007`** (only if you need one — see §3.2) ·
**`design-decisions.md` sections start at `## 24`**

**Run this alone.** It is the first slice where the ported AI pipeline meets a real user, and
it touches the one screen that is the app's whole point.

---

## 1. Mission

**I ask for an outfit in plain English and get one back — from my own closet, with reasoning
that cites real styling rules.**

Feature 007 ported three iterations of evaluated quality work and wired it to nothing. This
is the slice that finally calls it.

---

## 2. What already exists — read this before planning anything

The entire pipeline is on `rebuild` and has **zero callers from the API**. Your backend job
is mostly one route and a repository hand-off, not new pipeline logic.

| Already there | Where | State |
|---|---|---|
| The full LangGraph pipeline, 11 nodes | `pipeline/graph.py` | Complete |
| Entry point | `pipeline.graph.get_compiled_graph(repo)` | Complete |
| Deterministic-selection path | `pipeline/engine.py` | Complete |
| Grounding + citation enforcement | `pipeline/grounding.py`, `pipeline/cite.py` | Complete, see §2.1 |
| Scorers (5 dimensions) | `scoring/` | Complete |
| Retrieval (baseline / hybrid / advanced) | `retrieval/`, `kb.py` | Complete |
| Thread persistence | `memory/store.py::get_checkpointer` | Complete, see §3.2 |
| Response contract | `schema.SuggestResult` → `list[ScoredOutfit]` + `sources` | Complete |
| **The knowledge base, populated** | Qdrant `whattowear_kb` | **391 points, status green** — I verified L3/L4 rules are really in there |
| **A real `ClosetRepository`** | `repositories/supabase_closet.py` | **Already satisfies the Protocol** — see §2.2 |
| `/recommend` route + chrome | `frontend/app/(app)/recommend/` | Placeholder page |

### 2.1 The Principle IV citation gap is already closed — do not reopen it

`fix/007-citation-guard` is merged into `rebuild` (I confirmed with `git merge-base`).
`filter_ungrounded_cites` is the **enforcement**; `all_cites_grounded` stays a deliberate
read-only check. Both `pipeline/cite.py` and `pipeline/engine.py` apply the filter. If you
think you have found an ungrounded-citation hole, you are probably re-deriving a decision that
was already made and eval-verified — read `specs/007-ai-port/` first.

### 2.2 `SupabaseClosetRepository` already satisfies `ClosetRepository`

All three Protocol methods are present: `list_wardrobe_items`, `list_catalog_items`,
`get_derivation_inputs`. **You do not need an adapter.** Pass the repository straight to
`get_compiled_graph(repo)`.

⚠️ **But `get_derivation_inputs` is a stub that always returns `([], {})`** — its own
docstring says so. `memory/preferences.py` is ported and fed nothing. So preference memory is
inert, and **anything you build that appears to personalise on past feedback would be a
lie.** Leaving it stubbed is the right call for this slice; just do not build UI implying
otherwise, and say in your report that you left it.

⚠️ `ports.py`'s own docstring still claims *"No concrete Postgres-backed implementation
ships"* — stale since 004. Correcting that comment is welcome; changing the Protocol is not
(it is covered by the import-linter contract).

---

## 3. Scope corrections — read before planning

### 3.1 008 is the chat surface and a SINGLE-outfit reply. 009 owns the pager.

The design system describes the whole Recommend screen in one place, including the
multi-outfit pager. The split is at Recommend anatomy item 3: *"A reply proposing multiple
outfits instead renders the outfit suggestion pager"* — **that sentence is 009.** Everything
else on that screen is yours.

**The pipeline returns `outfits: list[ScoredOutfit]`, plural.** Render the top-ranked one.
Do **not** change the pipeline to return a single outfit — 009 needs the list, the evals
depend on the current shape, and `score_and_rank` already returns them ranked descending.

### 3.2 The checkpointer creates its own tables outside the migration system

`memory/store.py` uses `PostgresSaver` and calls `saver.setup()` itself, which creates
`checkpoints*` tables on first use. I confirmed **those tables do not exist in the database
today** — nothing has ever invoked the graph against it.

That is functionally self-healing, but it means `supabase db reset` produces a database whose
schema is incomplete until the first styling request, and those tables are invisible to the
migration story every other table follows. **Decide and record**: accept it (documented), or
add them as migration `0007`. Note that `PostgresSaver`'s schema is LangGraph's to change,
which is a real argument for *not* pinning it in a migration. Either answer is defensible;
an undocumented one is not.

Also confirm which URL it picks up: it prefers `database_url_direct` (session mode) over the
transaction pooler, and **falls back to `InMemorySaver` if neither is reachable** — in which
case threads silently stop persisting across a restart. Make sure you know which one you are
running on before you conclude anything about persistence.

### 3.3 Citations: in the bubble, never on the card

Two design-system statements look contradictory and are not:

- § Badge: the `citation` tone is *"used **only in Outfit detail's description**, never in the
  chat outfit card — the chat card's description is plain text with no citation markers."*
- Recommend anatomy item 3: assistant bubbles contain *"inline text segments plus inline
  numbered `citation` Badges"*, and below them *"a dashed top-border rule list."*

So: a **plain assistant reply** carries inline citation badges and a rule list. The **outfit
card** carries plain description text and no citation markers. Get this backwards and you
will have built the thing § Badge explicitly forbids.

### 3.4 `wardrobeMinItems` is config, not a constant

Design system: *"`wardrobeMinItems` = 5 in the prototype; **treat as a real config value, not
hardcoded copy**."* It gates the whole screen via `recommend.insufficient_closet.*`. Put it in
backend `Settings` alongside `wtw_closet_page_size`, and let the copy interpolate it.

### 3.5 Never display a number

Design system, emphatic: *"**No numeric score or percentage is ever displayed anywhere in the
UI.**"* `ScoredOutfit` carries `rank_score` and per-dimension `scores`; the match-score
thresholds map to a **label** only. Do not render the float, a percentage, or a debug
readout — not even behind a dev flag on a shared screen.

---

## 4. How to run this

```bash
git checkout rebuild && git pull
cd backend && uv sync
cd ../frontend && npm ci && npm run generate:api-types   # backend must be running
cd ../infra && npx supabase start && docker compose up -d   # Postgres AND Qdrant
```

⚠️ **This slice needs Qdrant running and populated**, not just Supabase. `infra/docker-compose.yml`
brings Qdrant up; the `whattowear_kb` collection already holds 391 points locally. If yours is
empty, ingestion is `ingest/cli.py` against `infra/corpus.yaml` with `$CORPUS_LOCAL_DIR` set —
**the corpus never lives inside this repo** (constitution Principle X).

⚠️ **`lib/api/schema.d.ts` is generated, not committed.** Regenerate after your route lands.

⚠️ A live LLM gateway is required (`AI_GATEWAY_API_KEY`). **No test may make a live call.**

```
/speckit-specify → /speckit-clarify → /speckit-plan → /speckit-tasks
                 → /speckit-analyze → /speckit-implement
```

Rename the branch Spec Kit cuts: `git branch -m feat/008-styling-chat`.

---

## 5. In scope

### 5.1 One backend route

Auth'd via 003's dependency. Builds a `SupabaseClosetRepository` for the caller, invokes the
compiled graph with a `thread_id`, returns the result.

Three things to decide and record:

**Item resolution.** `ScoredOutfit.items` is a list of **wardrobe item IDs**. The reply needs
56×56 thumbnails and deep links to `/closet/:itemId`, so the frontend needs real items with
`photo_url`s. Resolve server-side in the response, or make the client fetch each? Server-side
avoids N round trips and reuses 006's batch signing; it also widens the response contract.
Pick one, justify it.

**Thread identity.** `thread_id` is what the checkpointer keys refinement state on. Where does
it come from, who owns its lifetime, and what does "New chat" do to it? 011 will build chat
history on top of whatever you choose, so choose deliberately.

**Latency.** The pipeline does retrieval plus at least one LLM call and is **synchronous and
slow** — think seconds, not milliseconds. Decide the request shape (plain request/response
versus streaming) and set a real timeout. The calendar slice shipped a "works but takes a
fortune" experience that we are still carrying as a deferred gap; do not repeat it silently.

### 5.2 The insufficient-closet gate

Under `wardrobeMinItems` items, the screen shows `recommend.insufficient_closet.body` with the
"Add items to your closet" CTA and does not call the pipeline. Enforce it **server-side too** —
a client-only gate is a spec violation waiting to happen.

### 5.3 The Recommend screen

Per Screen anatomy — every element specified there is in scope except the pager:

1. `TopHeader` "Styling", subtitle *"Ask for an outfit, get cited picks from your closet"*,
   with **New chat** (`square-pen`) and **Chat history** (clock-with-arrow) as 36px siblings.
   New chat is **disabled, not hidden**, whenever the thread has no user turns — the design is
   explicit that archiving a blank session is forbidden. Chat history's destination is 011;
   wire the control, not the screen.
2. **Hero state**: 60×60 brand mark, wordmark, `"{greeting}, {name}"`, one assistant welcome
   bubble, three suggestion chips — "Rainy day commute", "Dinner date outfit",
   "Business casual". Greeting is **time-of-day based** (00–11:59 morning, 12–17:59 afternoon,
   18–23:59 evening, device local time); `known-gaps.md` records that the prototype hardcoded
   it.
3. **Chat state**: user bubbles right-aligned `--color-primary`, tail `14px 14px 4px 14px`;
   assistant bubbles left-aligned surface-sunken, tail `14px 14px 14px 4px`; 56×56 thumbnail
   row below a reply with items, each tappable → `/closet/:itemId`; dashed-top rule list for
   cited rules. Transient "Thinking…" row.
4. Calendar context line — "Style for an event from calendar", or "Styling for {event} ·
   Change". **012 already ships the calendar connection and picked events**; consume it.
5. "Start styling" full-width primary button once the user has sent a message, caption
   *"Uses everything you have told me so far"*.
6. Pinned pill input bar, placeholder "Style me…", 28px circular send button.

Chat column caps at **480px tablet / 560px desktop** — its own reflow, tighter than the
general cap.

### 5.4 Offline

Chat send disables via `navigator.onLine` (`lib/useOnlineStatus.ts`). Nothing queued, and no
copy promising a retry.

---

## 6. Explicitly out of scope

The multi-outfit pager and its feedback footer (**009**) · outfits gallery and detail, and
saving an outfit (**010**) · the chat-history screen and session archiving (**011**) ·
implementing preference memory (§2.2) · trends/weather enrichment beyond what the pipeline
already does on its own · any change to pipeline behaviour (§8).

---

## 7. Decisions already made — do not relitigate

| Topic | Decision | Source |
|---|---|---|
| Item selection | Grounded/deterministic per Principle II; the LLM writes rationale and picks from a scored shortlist | constitution II, `engine.py` |
| Citation grounding | `filter_ungrounded_cites` enforces; `all_cites_grounded` is a read-only check | `fix/007-citation-guard` |
| Repository | `SupabaseClosetRepository`. `ports.ClosetRepository` unchanged. | 004 / 006 / 007 |
| Corpus | Never in the repo. `infra/corpus.yaml` + `$CORPUS_LOCAL_DIR`. | constitution X |
| Score display | Labels only, never numbers | design-system § Match score |
| Taxonomy | Frozen | constitution VI |
| Generated schema | Not committed | design-decisions §20 |
| Form controls | Already built | design-decisions §1 |

---

## 8. Traps

1. **Do not write a second LLM call path.** Every call goes through `adapters/llm_gateway.py`
   and the pipeline. A parallel implementation is a Principle I violation.
2. **Do not change `ports.py`** — import-linter contract.
3. **Do not change pipeline behaviour.** `docs/eval-baselines/` holds recorded runs from three
   iterations. If your diff touches `pipeline/`, `scoring/` or `retrieval/`, you must re-run
   the evals and justify every movement. The cheapest correct answer is not to touch them.
4. **Citations on the bubble, not the card** (§3.3).
5. **No numbers on screen** (§3.5).
6. **Qdrant must be up.** A styling request against an empty KB returns no citations and looks
   like a pipeline bug.
7. **Regenerate `schema.d.ts`** after adding the route.
8. **Both CORS origins already work** — don't narrow the list.
9. **`design/prototype/` is reference only; `../app-legacy` is read-only.**
10. **No secrets, no corpus files, nothing from `data/` in the diff.**

---

## 9. Definition of done

- [ ] I type "business casual for a rainy commute" and get an outfit **built from my own
      closet items**, with reasoning that cites real rules from the KB.
- [ ] The thumbnails are real wardrobe items I own, and tapping one opens its Item detail.
- [ ] A closet under `wardrobeMinItems` shows the insufficient-closet state and never calls
      the pipeline — enforced server-side.
- [ ] A second message in the same thread refines rather than restarting (checkpointer works).
- [ ] "New chat" is disabled on an empty thread.
- [ ] No number, percentage or raw score appears anywhere on screen.
- [ ] `npx supabase db reset` from empty still applies `0001`–`0006` (plus `0007` if you added
      one), and a styling request works afterwards.
- [ ] Backend test count has not dropped (**617** on `rebuild` today).
- [ ] Frontend test count has not dropped (**182** today).
- [ ] `ruff`, `ruff format --check`, `mypy src`, `pytest`, `lint-imports`, `eslint`,
      `tsc --noEmit`, `next build` all clean.
- [ ] Eval baselines unchanged, or re-recorded with justification.
- [ ] **Checked in a browser** at `localhost:3000` *and* `127.0.0.1:3000`, both themes, all
      three breakpoints.
- [ ] No secret and no corpus file in the diff.

---

## 10. If you hit a gap

Start new `design-decisions.md` sections at **`## 24`**. §21 holds two deferred calendar
items; everything else there is decided.

This slice has four named decisions already — item resolution, thread identity, latency shape
(§5.1) and the checkpointer's tables (§3.2). `known-gaps.md` adds the time-of-day greeting.
**Record each with its alternatives; do not invent a value and move on.**

When you write `research.md`, the failure mode to guard against is not weak reasoning — it is
an **incomplete option list**. Feature 001 shipped a defect whose decision record was
well-argued but never considered the option that turned out correct. Ask what you have not
listed.

---

## 11. Report back with

What you built · how you resolved items into the reply and why · what `thread_id` is and who
owns it · what you did about latency and what a real request actually costs in seconds · what
you decided about the checkpointer's tables · whether the eval baselines moved · which
Constitution Check gates you could not satisfy · the §9 results · **what you saw in a
browser**, including one real styling reply end to end.

**Name what you skipped.** A report admitting two gaps is worth more than one claiming a
clean sweep.

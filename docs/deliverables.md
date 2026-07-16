# What to Wear — Certification Challenge Deliverable

This document addresses every deliverable in `docs/mvp-milestone-report.md`,
task by task, grounded in the actual state of this repository (`backend/` +
`frontend/`) rather than the original plan — where the two diverge, this
reflects what was built and verified.

---

## Task 1: Defining Problem, Audience, and Scope

### 1. The problem, in one sentence

> Deciding what to wear each day is a recurring source of wasted time and
> mental fatigue, especially for people who already own enough clothes to
> solve it.

### 2. Why this is a problem for the user

Anyone who dresses from their own closet faces this daily: before picking an
outfit, they have to reconcile several constraints at once — the occasion's
dress code, the weather, the mood or impression they want to convey, and
simple practicality (what's clean, warm enough, appropriate). The task isn't
choosing an outfit, it's finding the one combination, out of everything they
own, that satisfies all of these at the same time — even for something as
routine as a regular workday.

Today, people solve this by mentally cross-checking their closet against each
constraint one at a time: pulling out a few combinations, second-guessing
them, or defaulting to the same "safe" outfits just to skip the decision.
This works, but it's slow and error-prone — it's easy to miss one factor (too
warm, wrong dress code, clashing colors) until it's too late to fix, and
juggling several constraints against a whole closet's worth of options adds
up to real decision fatigue, even for occasions that shouldn't require much
thought.

### 3. Today's workflow diagram

![Today's workflow diagram](./assets/todays_outfit_decision_workflow.png)

**Tools/systems involved**: none, other than the closet itself, a mirror, and
a phone used only to text a photo to another person — there is no tool that
actually helps make the decision, only one that outsources it.

**Where it's slow, repetitive, or error-prone** (shaded above): there's no
starting point that narrows the closet before trial-and-error begins; the
occasion-vs-availability step is where hesitation sets in because nothing
has actually been filtered yet; and the mirror → text-a-friend → try-again
loop is the real bottleneck — it's repeated an unpredictable number of times,
depends entirely on someone else's availability and attention, and still
doesn't reliably produce the right outfit at the end (`K`).

### 4. Questions / input-output pairs to evaluate the application

These were used to seed the formal golden set built for Task 5
(`backend/data/golden_set.yaml`); shown here in plain product language.

| # | Input (what the user asks) | Expected output (properties, not a fixed outfit) |
|---|---|---|
| 1 | "What should I wear to an evening wedding, it's cold out (12°C)?" | Formal, includes a warm outer layer, avoids white/ivory, rationale cites a retrieved wedding/formality/weather rule |
| 2 | "Business-casual office look, it's freezing (-3°C)." | Business-casual base, a mandatory warm outer layer, every item actually owned by the user |
| 3 | "Hot beach day (31°C), feeling relaxed." | Casual, low-warmth pieces only, no outerwear/suits/gowns |
| 4 | "Job interview, cool weather (15°C)." | Business-casual to formal, conservative colors, no unnecessary outer layer |
| 5 | "Funeral, cool (10°C)." | Formal and subdued, explicitly avoids bright colors (red/yellow/green) |
| 6 | "Black-tie gala, cold (5°C)." | Black-tie formality actually reached, minimal accessories |
| 7 | Follow-up "warmer" after a date-night suggestion, same conversation | Same occasion/mood/weather preserved; only the warmth floor shifts up — not treated as a brand-new request |
| 8 | A request the closet genuinely can't satisfy (e.g. black-tie with no formalwear owned) | A graceful fallback with an explanatory note — never an invented item |
| 9 | A photo of a navy top, uploaded to add to the closet | Extracted category=top, a plausible formality range, a plausible warmth range (loose bounds — extraction, not a hard constraint) |
| 10 | "Suggest something," then "I don't like that, too much green" | A later, similar request avoids green without being told again |

---

## Task 2: Propose a Solution

### 1. The solution, in one sentence

> What to Wear is an AI stylist that assembles complete outfits only from
> clothes a user already owns, grounding every suggestion in retrieved
> professional styling rules and citing them, so getting dressed for any
> occasion takes one request instead of a mirror-and-friend loop.

### 2. Infrastructure diagram

![Infrastructure diagram](./assets/what_to_wear_system_architecture.png)

**Why each component:**

| Component | Choice | Why |
|---|---|---|
| **LLM** | `openai/gpt-5.4-mini`, called via the Vercel AI Gateway | Strong structured-output support at low per-request cost, which matters because a single suggestion makes several LLM calls (intent parsing implicitly via context assembly, outfit generation, rationale) |
| **Agent orchestration framework** | LangGraph (`StateGraph`) | Its built-in per-`thread_id` checkpointing is the entire mechanism conversational refinement ("warmer") runs on, and it gives a node-by-node trace for free |
| **Tool(s)** | Tavily (live trend search) + Open-Meteo (live weather) | Both are called as ordinary deterministic tool functions from graph nodes rather than LLM-invoked function-calling, because *which* layers to query is a fixed routing rule (Constitution Principle III), not something worth letting an LLM decide |
| **Embedding model** | `openai/text-embedding-3-small` | A solid quality/cost balance for a modest ~391-chunk corpus — no need for a larger embedding model at this scale |
| **Vector Database** | Qdrant (Cloud) | First-class hybrid dense-similarity **and** payload-metadata filtering in one store — exactly what the KB's structured-filter / load-all / dense-search split needs |
| **Monitoring tool** | LangSmith | Tracing is made *mandatory* in `config.py` (the app refuses to start without a key) — every real request gets a full per-node, per-call trace, the actual way to audit "why did it pick that" |
| **Evaluation framework** | A custom two-part harness: in-package deterministic checks + an isolated RAGAS/openevals project | Core grounding claims (owned-items-only, cites real rules) need to be verified *mechanically*, not judged — while retrieval and answer quality still benefit from RAGAS's and an LLM-judge's fuzzier metrics |
| **User interface** | Next.js (App Router) on Vercel | One deployable that satisfies "runs on my phone and laptop in a browser," with a fast CDN for static assets, for free |
| **Deployment tool** | Railway (backend + Redis) + Vercel (frontend) + Supabase (Postgres/Auth/Storage) | The minimum set of managed services covering compute, cache, relational data, auth, and file storage without hand-operating any infrastructure |
| **Other — reranker** | Cohere `rerank-v4.0-fast` | A cheap second-stage precision boost applied only to the one genuinely similarity-searched retrieval layer (current trends) — the structured layers have nothing for a reranker to improve |
| **Other — LLM routing** | LiteLLM (`langchain-litellm`'s `ChatLiteLLM`), sitting between LangChain and the gateway | Automatic same-provider retry on transient failures and LangSmith-visible cost/usage, without standing up a separate routing service |

### 3. Agent workflow diagram

 ![⚠️](There will be a proper diagram)

---

## Task 3: Dealing with the Data

### 1. Default chunking strategy, and why

The project uses **two chunking strategies, chosen per source type**, not
one universal splitter — because the two kinds of source content genuinely
need different treatment:

- **`atomic`** (the default for hand-authored/distilled content — dress-code
  definitions, weather-eligibility cards, harmony/proportion rules, trend
  cards): each document is already a single, self-contained rule, so it's
  kept as one chunk verbatim, with its `rule_id` preserved. This is what
  makes metadata filtering exact and citations stable — a rule can always be
  traced back to precisely the concept it states.
- **`section`** (the default for long-form prose — Wikipedia articles and
  two public-domain color-theory books): a `RecursiveCharacterTextSplitter`
  at a 900-character chunk size with 120-character overlap, using
  header-aware separators first. This avoids the "whole-article mush"
  problem of embedding a full article as one vector, while staying free and
  offline (no per-chunk API cost, unlike the semantic-chunking alternative
  the codebase also implements but deliberately never runs by default,
  since it costs an embedding call per sentence).

**Why this split**: rules that already exist as one atomic idea shouldn't be
artificially fragmented — doing so would only add noise and break precise
citation. Long-form prose, by contrast, has no natural atomic unit small
enough to embed usefully, so it needs real splitting. The resulting
chunk-size heterogeneity between the two source types is accepted
deliberately and measured directly (Task 6's chunk-size experiment below)
rather than papered over with one compromise size for everything.

### 2. Data sources and external APIs

---

## Task 4: Building an End-to-End Agentic RAG Prototype

### 1. Build

An end-to-end prototype is built and running: a FastAPI backend
(`backend/src/whattowear/`) implementing the full retrieval → generation →
scoring → grounding graph above behind `POST /suggest` (SSE), plus a Next.js
frontend (`frontend/`) covering sign-in/sign-up, add-item-by-photo (VLM
extraction with a user review/edit step before saving), closet view, and
free-text outfit suggestions with conversational refinement and a
like/reject reaction affordance.

### 2. Deploy

The prototype is deployed to public endpoints:

- **Backend** — FastAPI container on **Railway**, with `GET /health`
  checking live Postgres + Qdrant reachability (`503` naming the failed
  dependency if either is down, rather than a static `200 ok`).
- **Frontend** — Next.js on **Vercel**.
- **Data/auth/storage** — Supabase (Postgres, Auth, Storage bucket for
  wardrobe photos).

> **Live URLs**: They are provided in the submit form. 

---

## Task 5: Evals

### 1. Test data set

`backend/data/golden_set.yaml` — **24 hand-authored `(occasion, mood,
weather)` cases**, each with **expected outfit PROPERTIES, not a fixed
outfit** (an outfit problem legitimately has many right answers). Each case
specifies: a minimum formality floor, warmth constraints (a required outer
layer in cold weather, or a warmth ceiling in hot weather), forbidden
colors/categories where applicable, the specific `rule_id`s retrieval is
expected to surface (for retrieval recall), and a short reference answer
(for RAGAS). A second, independent **vision golden set** (`vision_cases`,
currently 2 samples — flagged in its own README as synthetic
placeholder images, not real garment photos, and explicitly not yet trusted
for a real accuracy claim) checks the photo→attribute extraction path with
loose expected ranges instead of hard constraints, since extraction is
inherently less precise than a closed-form rule check.

### 2. Evaluation harness

A **two-part harness**, matching the project's own deterministic-vs-fuzzy
split:

---

## Task 6: Improving Your Prototype

### 1. Advanced retrieval technique, and why

### 2. Comparison table

### 3. A second, independently-verified improvement
---

## Task 7: Next Steps

**Keep for Demo Day:** :)


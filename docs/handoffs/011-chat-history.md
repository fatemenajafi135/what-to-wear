# Handoff — Feature 011: Chat history

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/011-chat-history`, cut from
`rebuild` · **Migration number: `0011`** ·
**`design-decisions.md` sections start at `## 44`**

**Run this alone.** It adds the first persistence for conversations and touches the Recommend
screen that 008/009 own.

---

## 1. Mission

**I reopen a past conversation, read it back, and continue it.**

Nothing about a conversation survives a page reload today. `RecommendChat` holds the transcript
in `useState<ChatMessage[]>` and the `thread_id` in component state; refreshing the page loses
both, even though the pipeline's own checkpointed state for that thread is still sitting in
Postgres.

Feature 008 recorded this as explicitly yours to close — `design-decisions.md` §25: *"011's
'Continue' flow is what closes this gap by persisting session metadata (including its
`thread_id`) somewhere durable, which is out of scope here."*

---

## 2. ⚠️ Build the message model for feature 016, which is already scoped

**This is the one instruction that will look like over-engineering and is not.** Read it before
designing the schema.

Feature 016 (`docs/handoffs/016-conversational-turns.md`, decision recorded at
`design-decisions.md` §37) is scoped, decided, and waiting only on copy. It changes what a
transcript *contains*:

| | Today | After 016 |
|---|---|---|
| Assistant replies | one, per "Start styling" tap | one per user message, **plus** a wrap-up before the outfits |
| Message kinds | one | three — conversational turn, wrap-up, styling reply |
| Rough volume | ~2 messages per exchange | ~3× that |

If you persist today's shape, 016 needs a migration, a backfill decision, and a Session-detail
rework. So: **give the message row a `kind` discriminator from the start.** Today only
`styling_reply` (and the user's own messages) is ever written; 016 adds `conversational_turn`
and `wrap_up` as new values, not a new schema.

That is the whole accommodation — one column and a check constraint. **Do not build anything
else speculatively for 016**: no conversational endpoint, no slot storage, no UI for message
kinds that cannot yet occur. Anticipate the shape, not the feature.

---

## 3. Two gaps to resolve, both real

### 3.1 What is a "session", and what writes one?

There is no sessions table, and `thread_id` is the pipeline's own identifier minted by
`parse_request` — §25 chose that deliberately and it is not yours to change. You need durable
session metadata keyed on it: the preview text, the message count, the date, and the messages
themselves.

**"New chat" currently only resets.** The design system says it *"archives the current thread as
a Chat history session"*, but 008 built reset-only because there was nothing to archive into
(§28). With a sessions table there is. Decide what "archive" means concretely — is a session
written when it starts, or when it's archived? Written-on-start is the simpler model and
survives a browser crash; archive-on-demand risks losing everything the user just typed. Record
the choice — §44.

Note the design's own guard, already built: New chat is **disabled on a thread with no user
turns**, precisely so a blank session is never archived. Keep that true.

### 3.2 Outfits have no link to the conversation that produced them

The design requires an outfit count in two places:

- Chat history row: *"optional third line, only if the session produced outfits — an outfit-count
  line in `--color-primary`"*
- Session detail: *"only if the session produced outfits — a second full-width secondary button
  `{outfit count} → View in Outfits`"*

The `outfits` table has no `thread_id` or session reference — I checked the live schema. It has
`id, user_id, occasion, meta_line, rationale_text, match_label, item_ids, favorite, created_at,
updated_at, title, rationale_with_citations, citations, dimension_scores`.

Adding it is small: `POST /recommend/messages` has the `thread_id` in scope at the moment it
auto-saves each outfit (§42). Existing rows cannot be backfilled — decide what the count shows
for a session that predates the column, and say so.

---

## 4. In scope

### 4.1 Persistence and routes

Migration `0011`, following `0002`'s **RLS *and* GRANT** pattern, proven by a two-user test.
Ownership checked in the query as well — this backend's pooler role has `BYPASSRLS`, so a
route-level isolation test false-passes without it.

Routes: list sessions, get one session with its messages, and whatever "continue" needs. Extend
the existing router rather than adding a second one.

### 4.2 Chat history (`/history`)

Sticky `TopHeader` — title "Chat history", back arrow, right slot = `pill` **"New chat"**.

A vertically stacked list of session rows (`radius-md`, surface fill, bordered, 14px padding,
10px gap). Each row:

- **Top line**: session preview text (12.5px/700) with the date (10px secondary) right-aligned
  on the same line.
- **Second line**: message-count text (10.5px secondary).
- **Third line, only when the session produced outfits**: outfit count in `--color-primary`
  (10px/700).

At desktop this list sits beside a Session-detail pane, with *"Select a conversation to view
it."* when nothing is selected.

Copy is specified: `chat_history.empty.body`, `chat_history.error.body`,
`chat_history.error.cta`. Use it verbatim.

### 4.3 Session detail (`/history/:sessionId`)

`TopHeader` — title "Conversation", subtitle = session date, back arrow, **no right slot**.

The full **read-only** thread, same user/assistant bubble treatment as Recommend, **including
citation Badges** — but **no item-thumbnail rows and no rule lists** in the archived view. That
asymmetry is deliberate and specified; do not "fix" it by rendering the live treatment.

Below the thread: a full-width primary **"Continue conversation"** that resumes into Recommend
with that session's `thread_id`, and — only when the session produced outfits — a full-width
secondary **"{outfit count} → View in Outfits"**.

Session detail reflows exactly like Recommend (its own chat-column cap), not like a plain list.

---

## 5. Explicitly out of scope

Feature 016's conversational endpoint, prompt, slot extraction or copy — §2 is a schema
accommodation only · editing or deleting a past session unless you decide it belongs here (the
design specifies neither) · search across history · any change to `pipeline/`, `scoring/` or
`retrieval/` · exporting a conversation.

---

## 6. Traps

1. **Do not change pipeline behaviour.** `docs/eval-baselines/` holds three iterations of
   recorded work. If your diff touches `pipeline/`, `scoring/` or `retrieval/`, re-run the evals
   and justify every movement.
2. **Do not change how `thread_id` is minted.** §25 settled it; the pipeline owns it.
3. **`GRANT` as well as RLS**, proven by a two-user test.
4. **Archived view has citations but no thumbnails and no rule lists** (§4.3).
5. **New chat stays disabled on an empty thread** — a blank archived session is exactly what
   that guard exists to prevent.
6. **Regenerate `schema.d.ts`** after the routes land.
7. **Do not change `ports.py`** — import-linter contract.
8. **`design/prototype/` is reference only; `../app-legacy` is read-only.**

---

## 7. Definition of done

- [ ] I have a conversation, reload the page, and find it in Chat history.
- [ ] Opening it shows the full thread read-only, with citation badges and **without** thumbnail
      rows or rule lists.
- [ ] "Continue conversation" resumes into Recommend and a follow-up message refines the *same*
      thread rather than starting a new one. **Verify by inspecting the `thread_id` actually
      sent, not by reading the reply.**
- [ ] A session that produced outfits shows the count on both surfaces; "View in Outfits" lands
      on them.
- [ ] A session that produced none shows no third line and no second button.
- [ ] "New chat" archives the current thread and is still disabled on an empty one.
- [ ] Both empty and error states use the exact specified copy.
- [ ] Message rows carry a `kind` discriminator, with only today's values written (§2).
- [ ] **RLS proven**: user A cannot read user B's session or its messages.
- [ ] `npx supabase db reset` from empty applies `0001`–`0011`.
- [ ] Backend test count has not dropped (**692** on `rebuild` today).
- [ ] Frontend test count has not dropped (**291** today).
- [ ] `ruff`, `ruff format --check`, `mypy src`, `pytest`, `lint-imports`, `eslint`,
      `tsc --noEmit`, `next build` all clean.
- [ ] Eval baselines unchanged.
- [ ] **Checked in a browser** at `localhost:3000` *and* `127.0.0.1:3000`, both themes, at mobile
      *and* desktop widths — desktop is a two-pane layout.

---

## 8. If you hit a gap

Start new `design-decisions.md` sections at **`## 44`**. §37 is the conversational-turns
amendment you are building the schema for; §25 is thread identity; §42–43 are auto-save.
`docs/deferred-work.md` lists what is parked and deliberately not yours.

Named decisions: what writes a session and when (§3.1), and the outfit link plus what
pre-existing rows show (§3.2).

The failure mode to guard against in `research.md` is not weak reasoning — it is an **incomplete
option list**. §37 exists because §28 was well-argued, correctly rejected the two options it
considered, and never considered the third. Ask what you have not listed.

And: **check what actually reached the database, not that the request succeeded.** Four defects
have shipped on this project because a value was accepted with a 2xx and then silently dropped,
defaulted, or never written at all.

---

## 9. Report back with

What you built · what a session is and what writes one · how outfits link to a conversation and
what a pre-existing outfit shows · how you proved the same `thread_id` continues · how you proved
RLS · whether the eval baselines moved · the §7 results · **what you saw in a browser at both
widths.**

**Name what you skipped.**

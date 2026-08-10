# Quickstart: validating Recommend chat persistence

## Prerequisites

```bash
cd frontend && npm ci
cd ../backend && uv sync   # backend runs unmodified; needed only so the app has data to style
```

Start the stack as usual for this repo (`infra/`: `npx supabase start`; `docker compose up -d`;
backend `uv run …` dev server; frontend `npm run dev`). A closet with enough items to pass the
readiness gate (see `InsufficientClosetGate`) is required to reach the composer at all.

## Automated checks

```bash
cd frontend
npm run lint && npm run typecheck
npm test -- RecommendChat page.test.tsx recommendChatStore   # this feature's direct surface
npm test                                                      # full suite — count must not drop
npm run build
npm run e2e:pwa                                                # PWA e2e baseline (11) must not drop
```

## Manual validation (the part no test suite proves — do this in a real browser)

1. Open `/recommend`. Send a message (e.g. "business casual") and let the assistant reply.
2. Tap "Start styling" and let outfits render.
3. Navigate to Closet (or any other tab). Navigate back to Recommend.
   - **Expected**: the same messages and outfits are exactly as left — no hero-state flash, no
     loading skeleton, no network request for the conversation itself (readiness's own GET is
     expected and fine — FR-009).
4. Repeat step 3 two or three more times.
   - **Expected**: no drift — identical every time.
5. Send one more message, then immediately navigate away *before* the reply arrives. Wait a
   moment, then navigate back.
   - **Expected**: the reply is present, correctly placed, not stuck "Thinking…", not duplicated.
6. Tap "New chat."
   - **Expected**: hero state. Navigate away and back once more.
   - **Expected**: still hero state — the reset itself survives navigation.
7. Hard-reload the browser tab (or fully close and relaunch the installed PWA) with an active
   conversation.
   - **Expected**: hero state — a real reload still resets, unlike step 3.
8. From `/history`, open a past session via "Continue conversation" (`?thread_id=` link).
   - **Expected**: that session's prior turns load. Navigate away and back to plain `/recommend`.
   - **Expected**: the resumed conversation is still showing, not re-fetched or reset.

Every step above traces to an acceptance scenario in `spec.md` (User Stories 1–4) — this list is
the manual walkthrough of that acceptance criteria, not a separate set of checks.

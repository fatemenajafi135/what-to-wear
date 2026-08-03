# Handoff — Feature 016: Conversational styling turns

**From:** tech lead · **Status:** blocked on one item (§3) · **Branch:**
`feat/016-conversational-turns`, cut from `rebuild` · **Migration number: none expected** ·
**`design-decisions.md` sections start at `## 47`**

**Sequencing: unblocked.** 009 and 011 have both shipped. 011 deliberately built its message
model to accept this slice — `messages.kind` is a discriminator whose check constraint currently
allows `user_message` and `styling_reply` only (§44, migration `0011`). This slice **adds
`conversational_turn` and `wrap_up` to that constraint**; it does not reshape the table.

---

## 1. Mission

**I have an actual conversation with the stylist — it replies, asks what it needs to know — and
when I'm ready I tap "Start styling" and get outfits based on everything we discussed.**

Today the chat looks conversational but only the user talks. Nothing replies until "Start
styling" fires.

---

## 2. Read `design-decisions.md` §37 first

§37 amends §28 and contains the whole decision: what §28 got wrong, the evidence that changes
it, and the shape this must take. **Everything below assumes you have read it.** Do not
re-litigate it; do challenge it if you find something it missed, and say so in your report.

---

## 3. ⚠️ Blocked: the assistant's turn copy is not yours to write

`design-system.md`'s Recommend copy table has **four keys**, all error and empty states. There
is nothing for ordinary conversation. Principle VIII forbids inventing UI copy in code.

**The design owner is writing these lines.** The table below is a *draft for them to replace* —
it exists so the shape is agreed and nothing is forgotten, not so it can ship.

**Do not ship the draft.** Ask for the final copy before implementing anything user-visible. If
it has not arrived, build everything else and leave the strings in one module with a comment
pointing here.

| Situation | Draft (NOT final) |
|---|---|
| Acknowledge, nothing to ask | `Got it.` |
| Ask the occasion | `What's the occasion?` |
| Ask formality | `Is it a smart place, or more relaxed?` |
| Ask about weather | `Any weather I should plan around?` |
| Enough gathered | `I think I've got enough to work with — tap Start styling whenever you're ready.` |
| Turn cap reached | `Let's put this to work — tap Start styling and I'll pull some looks together.` |
| Wrap-up on Start styling | `Styling for {occasion}, {formality}.` |
| Conversational call failed | `I didn't catch that — try again, or tap Start styling with what we have.` |

Constraints the final copy must hold to, whatever the words: first-person stylist voice (the app
speaks as "I", never "we" or "the app"); one clarifying question per turn at most; never promise
anything the pipeline cannot deliver; the wrap-up must degrade gracefully when a slot is empty.

---

## 4. In scope

### 4.1 A new conversational endpoint

Separate from `POST /recommend/messages`. It takes the thread and the new message; it returns
**structured output** carrying both halves:

```
{ reply_text, occasion?, formality?, mood?, temp_c?, location? }
```

- **No retrieval, no wardrobe load, no pipeline invocation.** This is a small call.
- Through `adapters/llm_gateway` on the small chat model — **not a second way to call an LLM**
  (Principle I).
- Prompt lives in `prompts/` as a versioned file. **Inline prompt strings are prohibited.**
- `@traceable`, like every other LLM call site.
- Slot names match `GraphState`'s existing fields exactly. Do not invent new ones.

### 4.2 Slot accumulation and the wrap-up

Extracted slots accumulate across the thread — later turns overwrite earlier ones for the same
slot. On "Start styling", **Python composes the request from accumulated slots**, and passes
them to the fields `GraphState` already accepts. Raw user text remains the `occasion` fallback
when nothing was extracted.

**The pipeline does not change.** `pipeline/`, `scoring/`, `retrieval/` and `prompts/` for the
pipeline stay untouched, so `docs/eval-baselines/` cannot move. If your diff touches them, stop
and re-read §37.

Where accumulated slots live is yours to decide: the checkpointer already persists thread state,
which is the obvious candidate and needs no migration. Record the choice — §47.

### 4.3 The chat surface

Every composer send now calls the conversational endpoint and renders the reply as an assistant
bubble. `design-system.md` § **Chat input behavior** already specifies the behaviour, and its
production intent (not the observed prototype behaviour) is what to build: disable **both** the
input and the send button while `sending`, show a visible in-progress affordance on the send
button, and re-enable the instant the reply lands. The `sending` state shows the **"Thinking…"**
bubble; `styling` keeps **"Styling your outfit…"**. They are different states.

On "Start styling": the wrap-up renders as an assistant message, then the outfit group loads
beneath it.

Offline: the composer disables via `navigator.onLine` (`lib/useOnlineStatus.ts`). Nothing is
queued, and no copy may promise otherwise.

### 4.4 Quality bar for a new LLM path

Non-negotiable, and the reason this is a slice rather than a patch:

- **An entry in the golden set.** Evaluate the two halves separately: did it extract the right
  slots from a given utterance (checkable), and does the reply hold the voice (judge or
  loose check). Do not try to assert exact prose.
- **CI makes no live LLM calls.** Recorded fixtures only.
- **A turn cap per thread**, in `Settings` alongside `wtw_wardrobe_min_items`. Config, not a
  constant.

---

## 5. Explicitly out of scope

Any change to the styling pipeline · chat history persistence (**011**) · feeding conversation
into preference memory — `get_derivation_inputs` is still a stub returning `([], {})`, so
anything sent there vanishes while looking like personalisation · outfits gallery and detail
(**010**) · voice input · streaming the reply token-by-token.

---

## 6. Traps

1. **Do not change pipeline behaviour.** The evals are three iterations of recorded work.
2. **Do not ship the §3 draft copy.** Get the final lines.
3. **Do not write a second LLM call path** — `adapters/llm_gateway`, like everything else.
4. **No inline prompt strings.** `prompts/`, versioned.
5. **Do not let the model write `occasion` freely.** It gates retrieval; Python composes it
   from slots (§37).
6. **Do not change `ports.py`** — import-linter contract.
7. **Regenerate `schema.d.ts`** — the API surface grows.
8. **Qdrant must be running and populated**, or "Start styling" returns replies with no
   citations and it looks like a pipeline bug.
9. **`design/prototype/` is reference only; `../app-legacy` is read-only.**

---

## 7. Definition of done

- [ ] I send a message and the assistant replies, in the app's voice, using the **final** copy.
- [ ] It asks about a slot it does not have, and does not ask about one it already has.
- [ ] Sending disables the input and send button, shows "Thinking…", and re-enables when the
      reply lands.
- [ ] "Start styling" shows the wrap-up as an assistant message, then the outfits.
- [ ] Outfits reflect the conversation: a formality mentioned in turn 2 reaches the pipeline.
      **Verify this by inspecting what was actually passed to the graph, not by eyeballing the
      outfits.**
- [ ] The turn cap is enforced and configurable.
- [ ] A conversational-call failure degrades to a usable state; Start styling still works.
- [ ] `messages.kind`'s check constraint gains the two new values; existing rows are untouched
      and no table is reshaped (§44, migration `0011`).
- [ ] `pipeline/`, `scoring/`, `retrieval/` untouched; eval baselines unchanged.
- [ ] Golden-set entry exists for the new path and runs without a live call in CI.
- [ ] Backend test count has not dropped (**644** on `rebuild` today, plus whatever 009 adds).
- [ ] Frontend test count has not dropped (**247** today, plus 009).
- [ ] `ruff`, `ruff format --check`, `mypy src`, `pytest`, `lint-imports`, `eslint`,
      `tsc --noEmit`, `next build` all clean.
- [ ] **Checked in a browser** at `localhost:3000` *and* `127.0.0.1:3000`, both themes.

---

## 8. If you hit a gap

Start new `design-decisions.md` sections at **`## 47`**. §37 holds this slice's core decision;
§21 holds two deferred calendar items.

Named decisions still open: where accumulated slots live (§4.2), what the turn cap should be,
and what happens to accumulated slots after a Start-styling tap — does the next turn start
fresh, or keep refining? **Record each with its alternatives.**

The failure mode to guard against in `research.md` is not weak reasoning — it is an
**incomplete option list**. That is not a hypothetical here: §37 exists because §28 was
well-argued, correctly rejected the two options it considered, and never considered the third.
Ask what you have not listed.

And: **check what actually reached the database and the pipeline, not that the request
succeeded.** Three defects shipped on this project because a value was accepted with a 2xx and
then silently dropped or defaulted before it was stored or used.

---

## 9. Report back with

What you built · where accumulated slots live and why · what you passed to the graph on a real
Start-styling tap, shown as the actual values · how the golden-set entry evaluates the two
halves · whether the eval baselines moved · whether you received final copy or shipped with the
draft still flagged · the §7 results · **what you saw in a browser**, including one real
multi-turn conversation end to end.

**Name what you skipped.**

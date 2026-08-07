# Handoff — Feature 006: Photo upload + vision

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/006-photo-upload-vision`,
cut from `rebuild` · **Migration number: `0006`** · **`design-decisions.md` sections start at
`## 23`**

**Run this alone.** Wave A's three parallel slices produced five separate collisions and
every one cost more to untangle than the parallelism saved. This slice touches the closet
screens 004/005 own, the AI layer 007 landed, `config.toml`, and Storage — more shared
surface than any slice so far.

---

## 1. Mission

**I photograph a garment and it lands in my closet with its attributes already filled in.**

This is the slice that makes photos real. Every "photo" in the app today is a diagonal-stripe
placeholder; after this slice there are no placeholders left.

---

## 2. What already exists — read this before planning anything

Feature 007 ported the vision pipeline and **left it with zero callers.** Do not write a
second extraction path. Roughly half of this slice's backend is wiring, not writing.

| Already on `rebuild` | Where | State |
|---|---|---|
| VLM extraction, one structured-output call | `backend/src/whattowear/vision.py` | Complete, tested, **unused** |
| Its system prompt | `backend/src/whattowear/prompts/vision_system.md` | Complete |
| `ExtractedAttributes` (all-optional draft) | `schema.py:148` | Complete |
| `PhotoExtractionResponse` | `schema.py:169` | Complete |
| `CreateWardrobeItemFromUploadRequest` | `schema.py:177` | Complete — **but see §3.2** |
| Golden-case vision harness | `eval/vision_harness.py` | Logic ported; **cannot run, see §5.6** |
| Colour hex↔name model | `colors.py` | Complete — **but see §3.3** |
| `wtw_vision_model` setting | `core/config.py:63` | Falls back to `wtw_chat_model` |
| `/add` route + Create FAB/rail/sidebar launcher | `app/(app)/add/`, `components/shell/CreateLauncher.tsx` | **Chrome-only stub** — replace the body, keep the launcher |
| Online/offline hook | `frontend/lib/useOnlineStatus.ts` | Complete |
| `photo_path` column on both item tables | `0002_wardrobe_and_catalog_items.sql` | Exists, always null |

**What does *not* exist and is yours:** the Storage adapter, the bucket, Storage RLS, the
extract and create-from-upload routes, the entire Add-item UI, the camera primer, and real
photo rendering in the closet.

---

## 3. Scope corrections — the three things most likely to go wrong

I checked each of these against the design system, the live schema and the ported code.

### 3.1 The Storage adapter was deliberately NOT ported. Port it now.

`docs/legacy-ai-inventory.md` line 57 marks legacy `storage.py` (47 lines) **"adapt →
`adapters/`"**, and 007 did not do it. Read `../app-legacy/backend/src/whattowear/storage.py`
and adapt it — do not copy it.

Two things it gets right, keep both:

- **It uploads with the caller's own bearer token, never a service-role key.** Storage's
  per-`{user_id}` RLS policy is what enforces isolation, not application code. A service-role
  key would silently disable that.
- **Object path is `{user_id}/{uuid4}-{filename}`.** The `user_id` prefix is what the Storage
  policy matches on.

One thing it gets wrong for this codebase: it reads `os.environ` at module scope behind
`load_dotenv()`. **That breaks the zero-env import contract** —
`backend/tests/unit/test_import_safety.py` exists specifically to catch it, and its docstring
documents this exact mistake. Use `get_settings()` inside the function.

### 3.2 The review card and the required attributes do not match. This is a real gap.

Design-system Add item specifies **six review-card fields**: Name, Category (chips), Group,
Fabric, Color, Notes — *"every field is scan-auto-filled and every field is manually
editable."*

`CreateWardrobeItemFromUploadRequest` requires **eleven**, including `formality`, `warmth`,
`season`, `pattern` and `fit` — none of which appear on the review card, so the user cannot
see or correct them. Its docstring is explicit that these are required *here only*: "every
item saved through the photo flow must have every attribute populated, none blank."

So the design lets a user review six fields while five more are written from the VLM
unreviewed. Both halves are defensible on their own. **You must decide and record which
wins**: extend the review card beyond the design's field list (a Principle VIII problem), or
accept unreviewed attributes (all of them editable later via 005's edit form), or relax the
contract. Consider what happens when extraction fails entirely and all five are `null`
against a schema that requires them.

**Also fix, don't repeat, the Category/Group naming inversion.** The design's *"Category"*
chips (Tops/Bottoms/Outerwear/Shoes/Accessories) are our **`category_group`** enum, derived
on read by `categories.group_of()` and never stored. The design's *"Group"* text field
("Blazers") is our stored **`category`** column. 005 shipped a fix for exactly this
(`0f2657b fix(005): highlight the Category chip by group, not raw category`) — read it first.

### 3.3 "Color (text)" writes into a hex column

The design's review card has Color as a **text input**. `wardrobe_items.colors` is
`text[]` of hex, and `colors.py`'s opening docstring argues the point deliberately: *"hex is
the source of truth; names are derived, not stored… a name and a hex entered independently
drift apart with no safeguard."* `ExtractedAttributes` already normalises the VLM's colours
to hex on the way in.

A free-text field editing a derived value needs a decision: parse the typed name back through
`FASHION_COLOR_PALETTE` (fails on anything outside the curated list), swatch-pick instead of
type (contradicts the design), or accept text and match nearest. **Record the option list —
this is precisely the failure mode named in §10.**

---

## 4. How to run this

```bash
git checkout rebuild && git pull
cd backend && uv sync
cd ../frontend && npm ci && npm run generate:api-types   # backend must be running
```

⚠️ **`lib/api/schema.d.ts` is generated, not committed.** Regenerate after every pull that
changes backend routes and again after you add yours, or the frontend types the old API.

⚠️ **This is the first slice that needs a live VLM.** `WTW_VISION_MODEL` /
`WTW_CHAT_MODEL` and the gateway credentials must be set in `backend/.env` — see
`.env.example`. **No test may make a live call.** `vision.py`'s `_image_content_block` is the
pure seam for that; `backend/tests/unit/test_vision.py` shows the pattern.

```
/speckit-specify → /speckit-clarify → /speckit-plan → /speckit-tasks
                 → /speckit-analyze → /speckit-implement
```

Rename the branch Spec Kit cuts: `git branch -m feat/006-photo-upload-vision`.

---

## 5. In scope

### 5.1 Supabase Storage — bucket and policies

**No bucket exists.** Every `[storage.buckets.*]` block in `infra/supabase/config.toml` is
commented out.

**Declare the bucket in `config.toml`, not by hand in Studio**, unless you can argue
otherwise. A bucket created through the UI does not survive `supabase db reset` and is not
tracked — which breaks the reproducibility gate the constitution makes every migration meet,
and which the human's own DB reset just proved for the schema. If you do it another way, say
why in your report.

Storage RLS lives in migration `0006` as policies on `storage.objects`, matching
`(storage.foldername(name))[1] = auth.uid()::text`. **Follow `0002`'s pattern including the
table-level `GRANT`** — 004 found the backend's pooler role has `BYPASSRLS` and 013 found a
test fixture's blanket grant masking a missing one. **Prove isolation with a two-user test:
user A must not be able to read or overwrite user B's photo object.**

Decide and record: private bucket + signed URLs, or public bucket. These are photos of a
person's clothes in their home. Note what signed-URL expiry does to a cached closet grid.

### 5.2 Two routes

Extend `api/v1/routes/closet.py` — do not create a second router.

| Route | Shape |
|---|---|
| Extract | `multipart/form-data`, one image → `PhotoExtractionResponse`. Uploads to Storage, calls `vision.extract_attributes_from_image`, persists **nothing** to `wardrobe_items`. |
| Create from upload | `CreateWardrobeItemFromUploadRequest` → the saved item. |

**Extraction failure is a `200`, never a `5xx`.** A blurry photo with no garment in it still
uploads, still returns its `photo_path`, and returns `extraction_ok: false` with nulls — so
the user proceeds to manual entry without re-uploading. Only a genuine Storage failure 5xx's.
The legacy contract at `../app-legacy/specs/003-mvp-app/contracts/wardrobe-items-extract.md`
states this well; read it, and treat its status table as a starting point rather than a spec
to copy.

`422` for a missing file or an unsupported type. **Decide a max file size and enforce it** —
nothing in the design or the schema states one, and an unbounded multipart body reaching a
VLM is both a cost and a memory problem.

**`ports.ClosetRepository` must not change.** The AI pipeline consumes it and `ports.py` is
covered by the import-linter contract. Add to `repositories/supabase_closet.py`.

⚠️ Multipart request bodies do not round-trip usefully through
`openapi-typescript`. Check what `schema.d.ts` actually produces for the extract route before
you build the client call on top of it.

### 5.3 The Add-item flow

`app/(app)/add/page.tsx` is a stub that renders `TopHeader` + a placeholder paragraph.
Replace its body. **The launcher is done** — `CreateLauncher` plus the FAB (mobile), rail
button (tablet) and "+ New item" pill (desktop) already route here across all three tiers.
`/add` is an overlay flow, not a persisted destination; closing returns to the screen
underneath (`CloseAddOverlay` exists).

Flow: **dropzone → scan → review card(s) → saved**. Dropzone is full-width, `height: 220px`,
16px radius. Review-card photo is full-width, `height: 150px`, 16px radius. Layout is
stacked, one card at a time; centred at `max-width: 480px` from tablet up.

Copy is fully specified — use these keys verbatim, they are the assistant's first-person
voice and it is a stated convention:

| Key | Copy |
|---|---|
| `add_item.upload.placeholder` | tap to upload photo (garment scan) |
| `add_item.empty.body` | I couldn't find any clothing in that photo. Try a clearer, well-lit shot. |
| `add_item.empty.retake_cta` | Retake photo |
| `add_item.error.body` | That upload didn't go through. |
| `add_item.error.cta` | Try again |
| `add_item.bulk.title` | Add to Closet |
| `add_item.bulk.subtitle` | Choose how you would like to add items. |
| `add_item.bulk.option_title` | Add bulk items |
| `add_item.bulk.option_subtitle` | Upload several photos, one item each |
| `add_item.review.position` | Reviewing item {position} |

**Every form control already exists** — see `/dev/components` and `docs/design-decisions.md`
§1. Do not build new ones.

### 5.4 Bulk upload

In scope. Several photos, **one item each** — not several items per photo. Produces a queue
of review cards; **"Save & next"** advances, **"Save to Closet"** finishes.

`add_item.review.position` must be a **live-announcing `<h2>` with `aria-live="polite"`**,
not a `<span>` — design-system §7 names it explicitly. The overlay itself needs
`role="dialog" aria-modal="true" aria-labelledby="<heading id>"`; §7 records that as not yet
applied anywhere, so you may be the first to do it.

Decide and record: what happens when one card in a queue of eight fails to save.

### 5.5 Camera primer, and deleting the placeholder

**Primer.** `known-gaps.md`: wire `<input type="file" accept="image/*" capture="environment">`
*"gated behind the primer's Continue action"*, with a persisted **`wtw_camera_primed`** flag.
Feature 012 already built the calendar primer and its copy is in `design-decisions.md` §18 —
**follow that shape, don't invent a second one.** The camera primer's *copy* exists nowhere;
write it in the stylist voice and record it.

**Delete the placeholder.** Design-system §, verbatim: *"Once real photos replace the
placeholder, this striped pattern and its debug label should be deleted outright, not
preserved as a loading state (the skeleton blocks below are the actual loading treatment)."*

That means removing it from the **closet grid tile** and the **item-detail hero**, not only
from Add item, and rendering real photos there instead. This slice owns that — it is the
slice that makes photos exist. Handle the item with no photo (everything seeded before today)
as its own decision; the striped placeholder is not the answer.

Item detail's photo is full-width `220px` stacked on mobile, and **40% width on the left with
details on the right** from tablet up.

### 5.6 Close the vision harness gap 007 left open

`evals/golden_set.yaml` has two `vision_cases` pointing at
`fixtures/vision_samples/*.png`. **Those files do not exist** — `evals/fixtures/` contains
only `wardrobe.json`. `tests/unit/eval/test_vision_harness.py`'s docstring is candid about
it: the images *"were never actually present even in the legacy checkout — this golden-case
check has never been runnable, in either codebase,"* and sourcing real sample photos was
explicitly not 007's job.

It is yours: you are the slice that produces real garment photos. Add two sample images under
`evals/fixtures/vision_samples/` (Principle X's tracked-fixtures carve-out covers this) and
make `uv run python -m whattowear.eval.vision_harness` actually run. Use photos you are
entitled to commit — **do not commit anything from `data/` or any personal photo.** If you
cannot source them, say so plainly in your report rather than leaving the tests passing over
absent files.

### 5.7 Offline

Design-system §6: the upload trigger **disables** via `navigator.onLine` — `useOnlineStatus`
exists. Nothing is queued, and **the copy must not promise otherwise**; `known-gaps.md` §
spells out what a real Background Sync queue would require and it is not this slice.

---

## 6. Explicitly out of scope

Any catalog browse or catalog-add flow — **the word "catalog" appears zero times in the
design system**, and 005's handoff §2.1 already ruled this out · image cropping, rotation or
editing · multiple photos per item (*"no image gallery"*) · background removal · outfits
(010) · styling (008/009) · Serwist and cache strategies for the new images (014) · the
install prompt (015) · worn-count or favourite indicators on Item detail (005 §2.3 — still
excluded).

---

## 7. Decisions already made — do not relitigate

| Topic | Decision | Source |
|---|---|---|
| Vision and Principle II | Attribute extraction from a photo the user chose is metadata labelling, not outfit item selection. Settled. | `vision.py` docstring, constitution II |
| Extraction schema shape | `_EXTRACTION_SCHEMA`'s hand-written nullable-`required` form. Its docstring records the `BadRequestError` that produced it. | 007 |
| Every extracted field optional | A field failing must not block the others. | `ExtractedAttributes` |
| Taxonomy | Frozen. `category_group` and `formality_level` from `0001_init.sql`. | constitution VI |
| Colour storage | Hex only; names derived. | `colors.py` |
| Repository | Extend `supabase_closet.py`. `ports.ClosetRepository` unchanged. | 004 / 005 / 007 |
| RLS | Policies **plus** table-level `GRANT`, proven by a two-user test. | 004 / 013 |
| Migrations | Supabase only. Alembic is not used. | constitution |
| Form controls | Already built. Do not create new ones. | design-decisions §1 |
| Generated schema | Not committed. `npm run generate:api-types`. | §20 |
| Primer pattern | Established by 012. | design-decisions §18 |

---

## 8. Traps

1. **Never a service-role key for uploads.** The caller's bearer token, always — the per-user
   Storage policy is the isolation, not your code.
2. **No `load_dotenv()` or `os.environ` at module scope.** `test_import_safety.py` fails, and
   the failure will look unrelated to what you changed.
3. **No test makes a live VLM call.** Mock at `_image_content_block` / the gateway.
4. **`GRANT` as well as RLS**, on `storage.objects` too.
5. **Don't change `ports.ClosetRepository`** — the AI pipeline depends on its shape.
6. **Regenerate `schema.d.ts`** after adding routes.
7. **The VLM can return a category outside the frozen taxonomy.** That is a validation
   problem, not a licence to widen the enum.
8. **Both CORS origins already work** — `localhost` and `127.0.0.1`. Don't narrow that list;
   the closet's "Couldn't load your closet." error was this, once.
9. **`design/prototype/` is reference only.** Never copy code from it.
10. **`../app-legacy` is read-only.** Read it, never write to it.
11. **No secrets, and no photos from `data/`, in the diff.** `*.env` is gitignored for a
    reason.

---

## 9. Definition of done

- [ ] `npx supabase db reset` from empty applies `0001`–`0006` **and the photo bucket exists
      afterwards** with no manual step.
- [ ] **Storage isolation proven**: a test shows user A cannot read or overwrite user B's
      photo object.
- [ ] Photograph a garment → attributes arrive pre-filled → save → **it appears in the closet
      grid with its real photo**, and survives a reload.
- [ ] A photo with no garment in it returns `200` with `extraction_ok: false` and shows
      `add_item.empty.body` — not an error state, not a 5xx.
- [ ] Bulk: several photos queue, "Save & next" advances, the counter announces politely.
- [ ] **The diagonal-stripe placeholder is gone** from the closet grid and item detail.
- [ ] Camera primer gates the file input; `wtw_camera_primed` persists across a reload.
- [ ] Offline disables upload; no copy promises a retry.
- [ ] `uv run python -m whattowear.eval.vision_harness` runs, or its absence is reported.
- [ ] Backend test count has not dropped (**577** on `rebuild` today).
- [ ] Frontend test count has not dropped (**143** today).
- [ ] `ruff`, `ruff format --check`, `mypy`, `pytest`, `lint-imports`, `eslint`,
      `tsc --noEmit`, `next build` all clean.
- [ ] **Checked in a browser**, not just in tests — at `localhost:3000` *and*
      `127.0.0.1:3000`, in both themes, at all three breakpoints.
- [ ] No secret and no personal photo in the diff.

---

## 10. If you hit a gap

Start new `design-decisions.md` sections at **`## 23`**. §21 holds two **deferred** items and
§22 holds 005's two; everything else there is decided.

This slice has **six** named gaps already: the review-card field mismatch (§3.2), the colour
text field (§3.3), bucket privacy and signed URLs (§5.1), max file size (§5.2), a partial
bulk-save failure (§5.4), and the camera primer copy (§5.5). `known-gaps.md` names two more
that land squarely here — whether the review progress bar **animates or jumps**, and whether
**"Enter manually"** opens the same review form blank or a distinct flow. **Record each with
its alternatives; do not invent a value and move on.**

When you write `research.md`, the failure mode to guard against is not weak reasoning — it is
an **incomplete option list**. Feature 001 shipped a defect whose decision record was
well-argued but never considered the option that turned out correct. Ask what you have not
listed.

---

## 11. Report back with

What you built · where the bucket is declared and why · the Storage policy and how you proved
isolation · how you resolved the review-card/required-attribute mismatch · what you did about
colour · whether the vision harness runs and what images you used · which Constitution Check
gates you could not satisfy · the §9 results · **what you saw in a browser**, including a real
photo rendering in the closet grid.

**Name what you skipped.** A report admitting two gaps is worth more than one claiming a
clean sweep.

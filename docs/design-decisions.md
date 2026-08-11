# Design decisions

Resolutions for everything `design/design-system.md` leaves incomplete, ambiguous, or
self-contradictory, plus the form-control specification it never contains.

**Status of this file:** `design/design-system.md` remains the source of visual truth. This
document is the second half of that contract — it only ever *fills gaps* or *resolves
contradictions* in it, never overrides a value it states clearly. Where the two disagree,
that disagreement is called out explicitly below with a decision and a reason.

Every value here is derived from tokens already defined in §1.1/§1.2. Nothing is invented.

Every item here is decided except those explicitly marked **deferred** — recorded gaps awaiting a decision, not open questions blocking work.

---

## 1. Form controls — the missing component

The design system specifies 12 components, none of which is an input. The only mentions of
inputs anywhere are two token comments: `--radius-sm` *"controls: buttons, inputs,
chips-square"* and `--color-surface-sunken` *"wells: … input backgrounds"*.

Meanwhile inputs are required by: all four auth screens, the Add-item review card (6
fields), Item-detail edit mode, the Outfits-card inline rename, the chat composer, and
every section of Settings. This is the largest gap in the handoff.

### 1.1 Field anatomy

Every form field is a vertical stack with `--space-xs` (4px) between label and control:

```
Label            --font-size-xs (12px) / 700, --color-text-secondary, sentence case
[ Control ]      44px min height
Help or error    --font-size-xs (12px) / 400, --color-text-secondary or --color-error
```

(Sizes follow the rebuilt scale in §6, not `design-system.md` §2.)

Fields within a form are separated by `--space-lg` (16px). Help text and error text occupy
the same slot — an error replaces help text, never stacks below it, so field height stays
stable when validation fires.

### 1.2 `Input` — text, email, password, number

Matches `Button`'s geometry so a field and its `stretch` submit button align exactly (§5's
form-button rule requires this).

| Property | Value |
|---|---|
| Height | `44px` — satisfies the §3 hit-target minimum without a pseudo-element |
| Padding | `11px --space-md` (12px horizontal) |
| Font | **`--font-size-md` (16px)** / 22px line-height, weight 400 — see the iOS note below |
| Radius | `--radius-sm` (8px) — per the token's own comment |
| Background | `--color-surface-sunken` — per the token's own comment |
| Border | `1px solid --color-border` |
| Text | `--color-text-primary` |
| Placeholder | `--color-text-secondary` |
| Width | `100%` of its form column, always |

| State | Treatment |
|---|---|
| Default | as above |
| Hover (pointer only) | border → `--color-text-secondary` |
| Focus-visible | `outline: 2px solid --color-focus-ring; outline-offset: 2px` (see §4) |
| Filled | identical to default — no distinct filled style |
| Error | border → `--color-error`, 1px; error text below in `--color-error`; `aria-invalid="true"` and `aria-describedby` pointing at the message |
| Disabled | `opacity: 0.5` + `disabled` attribute, per §3's single disabled convention |
| Read-only | `--color-background` fill, no border-hover, still focusable and copyable |

**⚠ Input text is 16px at every breakpoint, and this is not negotiable.** iOS Safari
auto-zooms the page whenever a focused input has a font-size below 16px, then leaves the
viewport scaled — which in an installed PWA with no URL bar gives the user no obvious way
back. This is the single most common mobile web-form bug, and it silently breaks the app
shell's layout. It is the one place a control deviates from the body scale, and the reason
is mechanical, not aesthetic. Height math still resolves to exactly 44px: `11 + 22 + 11`.

**Password fields** carry a show/hide toggle: an `IconButton` at `size=28` inset at the
trailing edge, Lucide `eye` / `eye-off`, `aria-label` "Show password" / "Hide password",
`aria-pressed` reflecting state. The 44px hit-area pseudo-element applies and may overlap
the input's padding box.

### 1.3 `Textarea`

Identical to `Input` except: `min-height: 94px` (three rows at 16px/24px, plus the 11px
padding pair), `padding: 11px 12px`,
`resize: vertical`, line-height 1.5 to match the design system's stated treatment of the
Notes field. Used for Add-item **Notes** only.

### 1.4 `Select`

Native `<select>`, styled to match `Input` exactly, plus:

- Trailing Lucide `chevron-down` at 16px in `--color-text-secondary`, positioned with
  `--space-md` inline-end padding reserved for it.
- `appearance: none` with the chevron drawn as a background image, so the control is
  identical across platforms.
- Native select stays the implementation — it gets correct mobile pickers, keyboard
  behaviour, and AT semantics for free. **Do not build a custom listbox.**

Used for: Top size (XXS–XXXL), Bottom size (00–20), Shoe size, Height.

### 1.5 `DatePicker`

Native `<input type="date">`, styled as `Input`. Display formatting follows the design
system's one existing date example verbatim:
`toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })`.

Used for: Settings → Body & size → Birth date.

### 1.6 `TagInput`

Specified in Settings as *"free-text tag input (type + Enter to add a chip, × to remove)"*
and nowhere else. Composition:

- An `Input`-shaped container that grows in height as chips wrap.
- Each committed value renders as a `Chip` in its **active** state with a trailing `×`
  (Lucide `x`, 12px). Removal is a real `<button>` inside the chip with
  `aria-label="Remove {value}"` and the 44px hit-area pseudo-element.
- Enter commits the current text; Backspace on an empty field removes the last chip.
- The live text cursor sits inline after the last chip.
- `role="list"` on the chip group, `role="listitem"` per chip, and a visually-hidden live
  region announcing "{value} added" / "{value} removed".

Used for: Settings → Style preferences → "Brands to avoid".

### 1.7 Validation and error copy

The design system supplies form-level error copy (`auth.signin.error.body` and friends) but
no field-level messages. Rules, consistent with §9's copy conventions — sentence case, no
em dashes, name the problem and give one recovery:

| Key | Copy |
|---|---|
| `field.required` | This field is required. |
| `field.email.invalid` | Enter a valid email address. |
| `field.password.tooShort` | Use at least 8 characters. |
| `field.password.mismatch` | These passwords do not match. |

Validation fires on blur, never on keystroke, and re-validates on every change once a field
has already errored. Form-level errors (the existing `auth.*.error.body` strings) render in
a `Banner` with `variant="error"` above the first field.

**Confirmed:** the minimum is **8 characters**, not Supabase Auth's default of 6. Supabase's
`password_min_length` must be raised to 8 in project config so the server enforces what the
client claims — a client-only rule is not a rule.

---

## 2. Outfits gallery — grid or list?

**Contradiction.** §5's width-cap table says `2-col grid / 3-col grid / 4-col grid` and
groups Outfits with Closet as *"the two grid galleries"*. Screen anatomy says, in bold,
*"**List** (not a strict image grid): vertically stacked cards"*. §5 then contradicts
itself by also listing Outfits among the desktop two-pane wide-list screens — which cannot
coexist with a 4-column grid.

**Decision: it is a LIST.** Screen anatomy wins on three counts — it is far more specific
(card padding, gap, header row composition, the +N overflow chip in a 4-slot row), the
desktop two-pane arrangement requires a single-column list beside a detail pane, and the
gallery card's internal layout (title row, date line, thumbnail row) only makes sense at
list width.

§5's width-cap table row for "Outfits gallery" is therefore **wrong** and should read
`List / List, max-width 640px / wide list pane beside detail`, matching Chat history.
Closet remains a genuine grid at 2/3/4 columns.

---

## 3. Chat pager thumbnail grid — the 8-column value is impossible

§3 specifies 56px thumbnails with 6px gaps at *"8 columns at tablet/desktop"*. That needs
`8×56 + 7×6 = 490px`. Available width:

| Tier | Chat column cap | Card at ~92% | Minus 14px padding ×2 | Fits |
|---|---:|---:|---:|---|
| Tablet | 480px | 441.6px | 413.6px | **6 columns** (`6×56 + 5×6 = 366`) |
| Desktop | 560px | 515.2px | 487.2px | **7 columns** (`7×56 + 6×6 = 428`) |

**Decision: 4 columns at mobile (unchanged), 6 at tablet, 7 at desktop.** If a single
breakpoint above mobile is preferred for simplicity, **6 everywhere above mobile** is safe
at both tiers and I would take that trade.

---

## 4. Focus rings are invisible on primary buttons

`--shadow-focus-ring: 0 0 0 var(--focus-ring-offset) var(--color-focus-ring)`. The fourth
box-shadow value is *spread*, not offset — so the ring sits flush against the control. And
`--color-focus-ring` is the same hex as `--color-primary` in both themes (`#4B2E52` light,
`#C9A6D6` dark). A focused primary `Button` therefore gets a ring in its own fill colour
with no gap: it simply looks 2px larger. Fails WCAG 2.4.11 (Focus Appearance).

**Decision: replace the box-shadow with a real outline.**

```css
.control:focus { outline: none; }
.control:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: var(--focus-ring-offset); /* 2px — now a genuine gap */
}
```

`outline-offset` produces an actual gap, so the ring lands on `--color-background` and is
high-contrast against it in both themes. This also satisfies `known-gaps.md` §1's
`:focus-visible` requirement in the same rule, and outlines follow border-radius in every
current browser. `--shadow-focus-ring` is retired.

---

## 5. `--color-disabled` does not exist

§2's Caption row specifies `--color-disabled`/faint. No such token is defined in §1.2, and
§3 states the opposite rule outright: disabled is *"always `opacity: 0.5` +
`pointer-events: none` … **never** a dedicated 'disabled' color token."*

**Decision:** Caption uses `--color-text-secondary`. The reference to `--color-disabled` is
struck. Disabled styling everywhere remains the opacity convention.

---

## 6. The type scale — rebuilt

Two separate problems. First, the token scale (11/13/15/17/20/24/28) and the actual screen
text (26/16/13/12.5/10.5/10) share only two values, so body copy, labels and captions have
no token at all — making §1's *"every component reads only these names"* false for
typography. Second, the absolute sizes are too small.

**Evidence on the second point.** The prototype's device bezel (`ios-frame.jsx`) is
**402 × 874** — the iPhone 15 Pro logical viewport. So the type was authored at true device
scale; it was not shrunk by a simulator. That means 12.5px body and 10px caption are what a
real phone renders, and both fall below the platform floors:

- iOS HIG: avoid text below **11 pt** (1 pt = 1 CSS px at standard viewport scale). Caption
  at 10px and Label at 10.5px are below it.
- Material: body is **14 sp**; 12 sp is the caption floor. Body at 12.5px is below it.

There is also no responsive step anywhere — the same 12.5px serves a 402px phone and a
560px column on a 1440px monitor.

**Decision: apply a uniform ×1.12 multiplier to the whole scale, rounded to whole pixels,
then add one step at desktop.** A single multiplier preserves every ratio the designer
chose, so the visual hierarchy is unchanged — it is the same design, legible.

| Style | Design | **0–1023px** | **≥1024px** | Line height |
|---|---:|---:|---:|---|
| Display | 26 / 700 | **28** | **30** | 34 / 36 |
| Screen title `<h1>` | 20 / 700 | **22** | **24** | 28 / 30 |
| Section title `<h2>` | 16 / 700 | **18** | 18 | 23 |
| Card title | 13 / 700 | **15** | **16** | 20 / 21 |
| Body | 12.5 / 400 | **14** | **15** | 21 / 23 (1.5) |
| Label | 10.5 / 700 | **12** | 12 | 16 |
| Caption | 10 / 600 | **11** | 11 | 15 |

This replaces both the old UI scale and the untokenized display scale with one scale:

```css
--font-size-2xs:  11px;   /* Caption */
--font-size-xs:   12px;   /* Label, meta lines */
--font-size-sm:   14px;   /* Body, mobile + tablet */
--font-size-base: 15px;   /* Body desktop; Card title mobile + tablet */
--font-size-md:   16px;   /* Card title, desktop */
--font-size-lg:   18px;   /* Section title */
--font-size-xl:   22px;   /* Screen title, mobile + tablet */
--font-size-2xl:  24px;   /* Screen title, desktop */
--font-size-3xl:  28px;   /* Display, mobile + tablet */
--font-size-4xl:  30px;   /* Display, desktop */
```

The old `13px`, `17px` and `20px` steps are dropped — nothing used them. §2's statement
*"minimum body text anywhere is 10px"* is superseded: **the floor is 11px.**

**Two tiers only**, breaking at 1024px. Tablet shares the mobile scale deliberately — a
768px tablet is held at roughly phone distance, so it needs phone sizing, and fewer
breakpoints means fewer things to get wrong.

**Layout risk is low.** Every fixed-pixel box in the design (120px closet tile, 220px photo,
56px thumbnail, the skeleton blocks) contains an image or a placeholder, not text. The
text-bearing surfaces — Outfits cards, Calendar rows, Chat history rows, chat bubbles — are
all auto-height in the spec, so they absorb the change. The one visible consequence is that
`TopHeader` titles ellipsis-truncate slightly earlier, which is acceptable.

Per §8 of the design system, re-verify contrast numerically once this is set, especially
`--color-text-secondary` on `--color-surface-sunken`.

---

## 7. Shipped copy violates the copy rules

§9 states: *"**No em dashes.** Use a period, a comma, or two sentences instead."* Three
shipped strings use them.

| Key | Replace with |
|---|---|
| `recommend.insufficient_closet.body` | I need a few more pieces to work with. Add at least {wardrobeMinItems} items so I can put outfits together. |
| `item_detail.error.body` | This item couldn't be found. It may have been removed. |
| pager empty state | I couldn't put an outfit together from that. Try loosening a constraint or adding a few more pieces. |

The trailing phrase in the third still links to Add item, unchanged.

---

## 8. Match score — stored or derived?

§3 says each outfit *"carries a match score (0–1 float)"*. `known-gaps.md` §0.8 says the
label comes from *averaging the four sub-scores* — and calls that mapping "real logic that
should ship".

**Decision: derived.** The four sub-scores (`weather`, `formality`, `style`, `similar`) are
the stored data; the overall score is their average, computed at render time, thresholded
per §3's table. One source of truth, and it cannot drift from the per-dimension bars shown
right beside it in Outfit detail.

**Consequence the design system does not cover:** §3 says outfits scoring `<0.4` are
*"filtered out before reaching any surface"*, but `/outfits/:outfitId` is a real URL for a
saved outfit. **Decision:** the `<0.4` filter applies only to *newly generated suggestions*.
A saved outfit always renders at its detail route regardless of score — the user saved it
deliberately, and a 404 on their own saved outfit is worse than a low label. Match breakdown
still renders; the header pill is omitted below 0.4, per "not surfaced".

---

## 9. Routes vs. manifest shortcuts

The screen graph uses `/add` and `/recommend`. The manifest in `known-gaps.md` uses
`/?action=add` and `/?action=recommend`, and `start_url: "/?source=pwa"` — but `/` is not
in the screen graph at all.

**Decision:** real routes win. Manifest shortcuts become `/add` and `/recommend`.
`start_url` stays `/?source=pwa` for analytics attribution, and `/` is a redirect:
signed-out → `/signin`, signed-in → `/recommend`.

**Consequence:** §4 calls `/add` *"not a persisted destination — closing returns to the
screen underneath"*, which has no answer on a cold deep-link from the shortcut. **Decision:**
if `/add` is entered directly with no history, closing goes to `/closet` — the screen its
result lands in.

---

## 10. Smaller resolutions

| Issue | Decision |
|---|---|
| Boot/splash screen referenced three times (Display style, 32px logo, gated pulse) but absent from the screen graph | Not a route. It is the app-shell's pre-hydration state: centred `mark.svg` at 32px on `--color-background`, wordmark in Display style, pulse gated by `prefers-reduced-motion`. Belongs to feature 001. |
| §8's reduced-motion list names only 2 animations; later sections add 3 more | Gate all five: Switch thumb-slide, boot logo pulse, BottomSheet open/close, toast slide, and the pager's mobile transform-slide. |
| "+N" overflow chip is 52px beside thumbnails declared *"unified at 56×56px across every context"* | **56px.** Treated as a typo; a 4px mismatch in a 4-slot row is visibly misaligned. |
| Open Questions still asks whether the gallery-card heart toggles favourite directly | Resolved in §3 and Screen anatomy: **it does.** The Open Questions entry is stale; strike it. |
| §4 says "14 screens"; the tables list 15 | **15.** |
| Offline and error `Banner`s are visually identical (both `--color-surface-sunken`) despite §6 making them distinct and simultaneously visible | Offline keeps `--color-surface-sunken`; **error moves to a `--color-error` inline-start border, 3px**, retaining the same fill. Distinguishable without adding a colour. |
| `design-system.md` §7 says `viewport-fit=cover` "is already set"; `known-gaps.md` says it is conditional | Moot. We set it ourselves in feature 001. |
| `known-gaps.md` §0.6–§0.8 contain literal `—` / `§` escapes | Cosmetic mojibake from the export. Leave the file byte-exact as the received handoff; this note records it so nobody mistakes it for meaningful syntax. |

---

## 11. Closet sufficiency — a count is the wrong gate

`wardrobeMinItems = 5` blocks the styling request below five items. The concern raised
against it is correct: **five items does not guarantee an outfit can be built.** A closet of
five tops produces nothing, and the user would be let through the gate only to hit a failure
they cannot diagnose.

The count is measuring the wrong thing. From the salvaged enumerator, an outfit skeleton is
`top × bottom × footwear`, or `full_body × footwear`, optionally crossed with `outerwear`
when it is cold. So the real precondition is **slot coverage**, not volume:

```
(≥1 top AND ≥1 bottom AND ≥1 footwear)  OR  (≥1 full_body AND ≥1 footwear)
```

**Decision — three bands, not one threshold:**

| Band | Condition | Behaviour |
|---|---|---|
| **Blocked** | fewer than 5 items **or** slot coverage unsatisfied | Styling request is blocked. Copy names *what is missing*, not a number. |
| **Sparse** | coverage satisfied, but under 15 items | Request proceeds. A dismissible `Banner variant="info"` sets expectations. |
| **Normal** | 15 items or more | No banner. |

Both conditions must pass to leave the Blocked band — the five-item floor is kept
deliberately, coverage is added alongside it.

New copy, replacing `recommend.insufficient_closet.body`:

| Key | Copy |
|---|---|
| `recommend.insufficient_closet.body` | I can't put an outfit together yet. Add {missing} and I'll get started. |
| `recommend.insufficient_closet.cta` | Add items to your closet |
| `recommend.sparse_closet.hint` | I'm working with a small closet, so suggestions may repeat. Add more pieces for more variety. |

`{missing}` is a natural-language list of the unsatisfied slots — "a pair of shoes", "a top
and a pair of shoes". Naming the gap is actionable in a way that "add at least 5 items"
never is, and it removes the em dash the original string carried (§7).

The sparse banner is dismissible per session and must not reappear until the next session,
so it never becomes nagging.

**Both thresholds — 5 and 15 — are config values, not literals in copy.**

---

## 12. Auth flow

**Android is the platform we can test. iOS is built blind and verified later** — see
`docs/ios-verification-backlog.md`. This section decides the flow; everything
iOS-specific that cannot be checked without a device lives in that backlog.

### Decision

**Email + password is the primary flow, exactly as the design system specifies. Google
OAuth is the secondary. No magic link is ever sent for sign-in.**

That is not a compromise for iOS — it is what the design already specifies
(`auth.signin.error.body`: *"That email and password don't match"*, plus a Google button on
Sign in and Sign up). **The design system contains no magic-link sign-in anywhere;** the only
emailed link in the whole product is the password *reset* link. Nothing needed redesigning.

### Android: no special handling required

An installed PWA on Android is a WebAPK that **shares Chrome's storage and cookies**. There
is no separate container, OAuth returns to the app normally, and a session established in
the browser is visible in the installed app. Everything in the design works as written.

The requirements below are ordinary good practice, not Android workarounds:

1. Supabase client configured with `flowType: 'pkce'`.
2. Redirect to an **app route** — `/auth/callback` — never a Supabase-hosted page.
3. Every redirect URL on Supabase's allow-list.
4. Manifest `scope` must contain the redirect target. `scope: "/"` is already set by feature
   001, so any app route qualifies.

Requirement 4 does nothing on Android. **It is what makes the flow work on iOS**, so it is
built now even though its effect cannot be observed yet.

### Why no magic link, even though it works on Android

On iOS an installed PWA gets storage isolated from Safari. A magic link opens from Mail into
Safari, the session is written to Safari's container, and the installed app never sees it —
the user signs in successfully and returns to an app that says they are logged out. This is
**not fixable by configuration**; Supabase's own maintainers conclude a typed OTP code is the
only workaround.

Since the design never specified magic links, this costs nothing today. It is recorded so
nobody adds one later as a convenience and quietly breaks iOS. If a passwordless option is
ever wanted it is **email OTP** — a typed code, which keeps the user inside the app — and
that needs a code-entry screen the design system does not contain, making it a design
change rather than an implementation detail.

### Password reset — do not "improve" it

The reset link opens in the browser, the user sets a new password there, and
`auth.reset.success.cta` sends them to `/signin` rather than into the app. **No session
crosses a storage boundary**, so this works identically on both platforms.

Keep it exactly as specified. Signing the user in automatically after a successful reset
would create precisely the cross-container handoff described above — and it would work fine
on Android and every desktop browser, failing only on installed iOS, which is the hardest
possible place to notice it.

---

## 13. Auth panel's desktop treatment — radius and internal padding

§5's content-width-caps table says the desktop auth panel gains a `--color-surface` fill and
a 400px max-width, but specifies no radius, padding, or shadow for it — the only container in
the whole system introduced without one. No `--shadow-*` token exists anywhere in
`tokens.css`, so inventing one here would be the exact violation Principle VIII exists to
prevent.

### Decision

`--radius-md` (14px, "cards" per its own token comment) and `--space-2xl` (32px) internal
padding. No border, no shadow.

**Radius**: the panel is a static, non-modal content container — closer to a card than to a
sheet/modal (`--radius-lg`, reserved for those per its comment) or a control
(`--radius-sm`, buttons/inputs). `--radius-md` is the only token whose own stated purpose
matches what this panel actually is.

**Padding**: `--space-2xl` sits between the form's own `--space-lg` field gaps and the
screen-level `--space-xl` mobile padding — enough to read as a distinct raised surface
around the form rather than a tight inset.

**No shadow**: adding one would be inventing a value with no token to read it from. If a
future design pass adds `--shadow-*` tokens, this panel should pick one up as a normal
follow-on, not as a special case tied to this decision.

### Alternatives considered

- `--radius-lg` (sheets/modals) — rejected: this panel isn't a dismissible overlay, and using
  the modal radius would visually conflate two different kinds of container.
- A border (`1px solid --color-border`) instead of/alongside the surface fill — rejected: no
  other card-like container in the system pairs the surface fill with a border; adding one
  here would be a second invented value, not a resolution of the first.

---

## 14. Auth screen navigation copy — submit labels and cross-links

`design-system.md` §6's Auth copy table has error/sent copy for all four screens, but no
copy for the ordinary controls a working auth flow needs and none of the four routes can
function without: each screen's submit-button label, the Sign in ↔ Sign up cross-link, and
`/forgot-password`'s only entry point (nothing links to it from `known-gaps.md` or the route
table either — §4 lists the route but never says what triggers it).

### Decision

Sourced from `design/prototype/`'s own copy (reference-only per the ground rules, read for
intent — not code, just the strings its author already chose for this exact problem):

| Screen | Element | Copy |
|---|---|---|
| Sign in | Submit button | Sign in |
| Sign in | Link below password field | Forgot password? → `/forgot-password` |
| Sign in | Cross-link | Don't have an account? **Sign up** → `/signup` |
| Sign up | Submit button | Create account |
| Sign up | Cross-link | Already have an account? **Sign in** → `/signin` |

"Create account" rather than repeating "Sign up" as both the screen's own name and its
button label — the prototype's own reasoning, and it reads better than the stutter.

### Alternatives considered

- Inventing new copy instead of using the prototype's — rejected: the prototype already
  solved this exact problem, its copy fits the same sentence-case/no-em-dash rules §9
  requires everywhere else, and re-deriving it from scratch risks a worse answer to a
  solved question for no benefit.
- Leaving `/forgot-password` with no in-app entry point — rejected: the spec requires the
  route to be reachable (User Story 3), and the prototype's placement (a small link directly
  under the password field) is the only entry point it defines anywhere.

---

## 15. Google button when the provider isn't configured

Neither `design-system.md` nor this doc's §12 says what Sign in/Sign up's Google button
should look like when Google OAuth isn't wired up server-side. That state is real: it's
whatever Supabase's `[auth.external.google]` reports today, in any environment, whenever the
client ID/secret are unset. §6's `auth.signup.error.body` / `auth.signin.error.body` don't
fit it either — both are about a submitted email/password not matching, not about a
provider being unavailable before the user does anything.

It also isn't a case the normal form-error mechanism (§1.7's `Banner variant="error"`) can
even reach. `supabase-js`'s `signInWithOAuth()` never rejects: it resolves `{ error: null }`
and then does a real `window.location.assign()` to GoTrue's `/authorize` endpoint. If the
provider is disabled there, GoTrue serves its raw JSON 400 as the response body of a full
page navigation — the SPA has already been left, so no `catch` in React ever runs. Any
fix has to prevent the click before that navigation starts, not react to it afterward.

### Decision

**Disable the button** using the convention that already exists for every other control —
`opacity: 0.5` + `pointer-events: none` via the native `disabled` attribute (§3, decision
§5) — driven by a live check against GoTrue's public `GET /auth/v1/settings` endpoint
(`{ external: { google: boolean } }`). This is the same signal Supabase's own server uses
to decide whether `/authorize` will work, so the button can't drift out of sync with the
backend the way a duplicated frontend env flag could. The check defaults to "unavailable"
until it resolves (fail closed): a slow or failed settings fetch leaves the button disabled
rather than briefly offering one that's about to 400.

No new copy or visual state was invented — the button stays visible on both screens (it is
specified there) and, when disabled, looks like every other disabled control in the system.

### Alternatives considered

- **Hide the button entirely** — rejected: the task and the design both keep Google
  specified on Sign in/Sign up; disabled communicates "not right now," hidden would make it
  look never-planned and would need to reappear/disappear per-environment, which is more
  moving parts than one boolean.
- **Catch the error and show a `Banner`** — rejected on the mechanics above (there's nothing
  to catch), and even a redesigned version that checked availability *before* calling
  `signInWithOAuth()` would need new copy `design-system.md` doesn't have (`auth.*.error.body`
  is about credentials, not provider availability) — inventing that copy silently is exactly
  what the task said not to do, whereas the disabled state needed none.
- **A build-time `NEXT_PUBLIC_GOOGLE_AUTH_ENABLED` flag instead of the live settings check**
  — rejected: it's a second, independently-maintained copy of information Supabase already
  exposes, and the two can silently disagree (flag says enabled, GoTrue says no, or vice
  versa) in a way the live check structurally cannot.

Implementation: `frontend/lib/supabase/useGoogleAuthAvailable.ts`, consumed by
`SignUpForm`/`SignInForm` to set `GoogleButton`'s `disabled` prop.

---

## 16. Calendar OAuth token storage

Neither `design-system.md` nor this document said how a third-party OAuth token — the first
one this project holds — should be stored. Feature 012's handoff flagged this exact gap as
likely and asked for it to be recorded here rather than defaulted silently into the existing
wardrobe-item pattern (query-level filter + RLS as convention), which was never evaluated
against holding a credential usable outside this application entirely.

### Decision

`calendar_connections.access_token`/`refresh_token` are encrypted at the application layer
(`cryptography`'s `Fernet`) before being written to Postgres, decrypted only inside the
repository layer immediately before a live Google API call, and never included in any API
response, error message, or log line. Key: `WTW_TOKEN_ENCRYPTION_KEY`, a new backend setting,
blank in `.env.example`.

Full reasoning, including why RLS alone is not sufficient here (`specs/004-closet-read/
research.md` §1 already found the app's own pooler connection bypasses RLS entirely) and the
alternatives considered (plaintext + RLS-only, a managed KMS/Supabase Vault, refresh-token-only
storage), lives in `specs/012-calendar/research.md` §2 — this entry exists so the decision is
discoverable from the same document every other cross-cutting choice lives in, not to
duplicate that reasoning.

---

## 17. Connected accounts' Google Calendar — what actually triggers disconnect

`design-system.md` §4 describes Connected accounts' Google Calendar row as "a connect/disconnect
toggle (shows a 'Connected' status Badge when linked, a 'Connect' text action when not)." That
sentence names an affordance for the *not-linked* case (a text action) but only a **display**
element for the *linked* case — `Badge` is specified elsewhere (§3) as display-only, with no
interactive states of its own. Taken literally, a connected user would have no way to disconnect
at all.

### Decision

When linked, the row shows the "Connected" `Badge` **plus** a "Disconnect" text action beside
it — the same visual treatment (plain underlined text button) as the "Connect" text action
already specified for the not-linked case, just the mirror-image label. No new component is
introduced; this reuses the exact text-action pattern the design system already names for the
opposite state.

`/calendar` itself never gains a disconnect affordance — its screen anatomy (§6, "Screen
anatomy → Calendar") only ever describes a connect action, present in the disconnected card.
Once connected, `/calendar` has no disconnected card to put a disconnect action on, and no
other affordance is specified for one. Settings → Connected accounts is therefore the *only*
place a user disconnects, which is a valid reading of "two entry points" (both places can
*connect*; only one shows a *connected* state with something to act on).

### Alternatives considered

- **Tapping the `Badge` itself toggles disconnect.** Rejected — `Badge` is documented
  system-wide as a display-only pill (§3); overloading it with a hidden interactive behavior
  contradicts its own spec and gives keyboard/AT users no discoverable way to reach it (no
  visible affordance, no accessible name suggesting an action).
- **Add a disconnect action to `/calendar`'s connected states too**, so both entry points are
  fully symmetric. Rejected — the design system's screen anatomy for Calendar's connected
  states (event list, empty) names no such control, and design-decisions.md exists to resolve
  silence or contradiction, not to add UI the design never specified in the first place
  (Principle VIII, the same direction this document's other entries are careful not to
  violate).

---

## 18. Calendar permission primer — copy

`known-gaps.md` §-2 requires a primer card before the real Google consent screen and names its
primary action's label verbatim ("Continue to Google"), but neither it nor `design-system.md`
specifies the primer's title or body copy, and `design/prototype/` has no working primer to
read intent from (searched — no match).

### Decision

| Element | Copy |
|---|---|
| Title | Before you connect |
| Body | I'll be able to see your event titles, times and locations so I can suggest outfits for what's actually on your schedule. You can disconnect anytime from Settings. |
| Primary action | Continue to Google |
| Secondary action | Not now |

First-person stylist voice ("I'll be able to see... so I can suggest"), matching
`calendar.disconnected.body`'s existing voice ("so I can suggest outfits for what is actually
on your schedule") rather than switching to a neutral system voice — this primer is a
continuation of the same connect action, not a distinct system-level notice like the offline
banner. Sentence case, no em dash, one recovery-shaped action pair, per §9's copy conventions.

Rendered as a bespoke card in the same `<dialog>`-based, real-modal-semantics shape
`BottomSheet` uses (safe-area-aware bottom padding, focus trap via `showModal()`) rather than
reusing the `BottomSheet` component directly — its API is label-only rows and has no slot for
body text, and `design-system.md` §3 already names this exact situation ("Bespoke variants not
on this component... richer than BottomSheet's plain label rows") as the documented escape
hatch, not a violation of "don't build form components" (a primer card is content, not a form
control).

### Alternatives considered

- **Neutral/system voice** ("You'll be able to see event titles, times and locations…") —
  rejected: breaks voice consistency with the disconnected card's copy one tap away, for no
  stated reason in §9's exception list (which reserves neutral voice for connection/sync
  *status*, not a connection *action*).
- **Reuse `BottomSheet` verbatim with the explanation squeezed into the title.** Rejected —
  loses the explanation entirely (titles are short, "13px/700" per §3) or forces multi-line
  text into a slot the component doesn't support, when a bespoke variant is already the
  system's documented answer for this exact shape of content.
## 19. Feature 013 (Profile & Settings) — three design-system gaps resolved

### 16.1 Profile's "three cards" — contents

`design-system.md` says "three cards" three times (§2's type-scale note, §5's responsive
table, §8's accessibility note) but never names what the three are. `design/prototype/`
shows a materially different, superseded split (Style preferences and Body & size as
*editable* cards directly on its "Profile" screen, with Account/Connected/Notifications only
reachable via a separate "Settings" screen) that contradicts the current spec's "Settings has
all five sections, Profile has none of the controls" model, so it isn't load-bearing here.

**Decision**: the three cards are **Account** (email), **Style preferences** (style tags +
colour tags only — "Brands to avoid" is omitted from the summary), and **Body & size** (body
shape, gender, birth date, height, sizes — whichever the user has set). Account gives the
screen an identity anchor since the current design-system text specifies no avatar/name
header for Profile; Style preferences and Body & size are the two sections spec.md itself
calls the core declared-taste data this feature exists to capture (both P1 user stories).
Connected accounts and Notifications stay Settings-only, consistent with them being the
explicitly lowest-priority section pair in spec.md.

### 16.2 Body-shape illustrations — stroke weight and size

On `design-system.md`'s own "Open questions" list: *"the 5-option body-shape selector needs a
stroke weight/size spec for its line-art silhouettes if rebuilt without the source SVGs."*

**Decision**: filled (not stroked) geometric silhouettes — a circle for the head plus one or
two polygons per shape for the torso/hip line — at a `32×44` viewBox. Rendered at `26×36px` in
the read-only summary (Profile card, Settings read state) and inside a `64×84px` option box in
the edit-mode picker (`BodyShapePicker`). Matches the proportions the prototype's own
placeholder art implies (reference for intent only — no markup or coordinates were copied;
`BodyShapePicker.tsx`'s five polygons are independently authored).

### 16.3 Settings Edit/Done toggle — visual treatment while editing

Also on `design-system.md`'s "Open questions" list: *"does the toggle button change
color/style while in 'editing' mode, or only its label swaps?"*

**Decision**: label-only swap ("Edit" ↔ "Done"); the button's color, border, and background
stay identical in both states. Consistent with this document's own minimalism precedent (§5:
no new visual state invented without a token backing it) — inventing a distinct "editing"
button style would be exactly that.

---

## 20. Reconciling features 004 and 013's independent `frontend/lib/api/` decisions

004 (closet) and 013 (profile/settings) were developed in parallel, against the same base,
each the first slice to need the other's not-yet-existing file. Both independently built
`frontend/lib/api/client.ts` and both independently decided how `schema.d.ts` gets produced —
and disagreed on both. Merging `rebuild` (which already carries 004) into 013 surfaced the
collision as a real merge conflict plus a broken `next build` (`no exported member 'apiClient'`
in `ClosetGrid.tsx`), not a paper one.

### 17.1 One client module: `openapi-fetch` base, 013's `ApiError` layered on top

**Decision**: `frontend/lib/api/client.ts` keeps 004's `openapi-fetch`-based `apiClient`
(typed against the generated `paths`, so a call to a route or param name that doesn't exist
is a compile error — something a hand-written wrapper cannot give) as the base, and adds back
013's `ApiError`/`unwrap`: a thin function that turns `openapi-fetch`'s non-throwing
`{ data, error, response }` result into a thrown `ApiError` (carrying the real HTTP status)
for call sites that prefer throw/catch. `frontend/lib/api/profile.ts` was rewritten to call
`apiClient.GET`/`.PATCH` and pass the result through `unwrap`; `ClosetGrid.tsx` and
`[itemId]/page.tsx` are untouched — they already destructure `{ data, error }` directly from
`apiClient`, which the merged client still returns exactly as before.

**Rationale**: `openapi-fetch`'s compile-time route/param checking is what Constitution
Principle VII's "frontend MUST consume types generated from OpenAPI" actually implies —
013's original `apiFetch<TResponse>(path: keyof paths, ...)` only checked that `path` was a
known key, not that the method, request body, or response shape for that path matched. Losing
`ApiError`'s typed failure handling (a real, if small, regression) is avoided by keeping it as
a composable helper rather than a competing client.

**Alternatives considered**:
- *Keep 013's hand-written `apiFetch`, rewrite `ClosetGrid.tsx`/`[itemId]/page.tsx` onto it.*
  Rejected — explicitly out of bounds (004's screens are correct on their own terms), and it
  throws away `openapi-fetch`'s compile-time route/param checking for no gain.
- *Keep both clients under different names/files (e.g. `client.ts` and `fetchClient.ts`).*
  Rejected — two ways to call the same backend from the same frontend is the "two sources of
  truth" failure mode this whole document exists to avoid elsewhere (see §12's single Supabase
  client instance, §8's one match-score source); it would also leave the next feature to
  guess which one to extend.
- *Drop `ApiError` entirely and have 013's sections handle `{ data, error }` inline like
  `ClosetGrid.tsx` does.* Considered seriously — it would remove `unwrap` entirely. Rejected
  because 013's Edit/Done sections are written as `async function done() { ... }` bodies where
  throw/catch reads more naturally against a draft-commit flow than a `data`/`error` branch at
  every call site; `unwrap` is small enough (nine lines) that keeping both idioms available,
  rather than forcing one shape on every future caller, isn't the kind of speculative
  abstraction the constitution's Quality Bar warns against — it's an existing concern (013
  shipped it) being preserved, not a new one being invented.
- *An option not initially on this list, worth naming explicitly since an incomplete option
  list is the named failure mode to guard against here*: making `unwrap` throw the real
  Pydantic `detail` validation message instead of a generic `"Request failed"` string, by
  reading `result.error` (FastAPI's `422` body). Not done — no call site currently surfaces
  field-level server error text to the user (Settings' sections show the shared
  `settings.error.body` copy per design-system.md §6, not per-field server messages), so this
  would be unused code today. Flagged here rather than silently built or silently dropped, in
  case a future feature needs it.

### 17.2 `schema.d.ts`: generated at build/CI time, never committed

**Decision**: adopt 013's approach. `git rm --cached frontend/lib/api/schema.d.ts`; the
`.gitignore` entry (already present from 013) is what's authoritative going forward.
`.github/workflows/ci.yml`'s frontend job now installs `uv`, installs backend dependencies,
starts `uvicorn` with placeholder `DATABASE_URL`/`SUPABASE_URL` values (`/openapi.json` is
served from route/type definitions alone — FastAPI never touches the database to build it, so
this doesn't need Supabase running, only `Settings()` to construct, matching
`test_whoami.py`'s existing fake-env pattern), waits for it to answer, then runs
`npm run generate:api-types` before lint/typecheck/build. A fresh clone follows the same
sequence documented in `specs/013-profile-settings/quickstart.md` §4 and `frontend/package.json`.

**Rationale**: 004's `research.md` §8 committed the file reasoning "CI has no live backend to
query," true at the time — 004's own CI job never started `uvicorn`. That premise doesn't
survive a second feature adding routes in parallel: a committed snapshot reflects whichever
branch generated it last, and neither 004 nor 013's copy could see the other's routes,
because commit order isn't merge order. The deeper issue is that `schema.d.ts` isn't
"append-only" the way `infra/supabase/migrations/*.sql` is — each migration is a permanent,
independent addition nothing else overwrites, so two features' migrations coexist by
construction. `schema.d.ts` is a single whole-state snapshot that a second feature's commit
necessarily *replaces*, not extends — closer to a lockfile than a migration, and this
project's own lockfiles (`package-lock.json`, `uv.lock`) are already committed-but-regenerated
artifacts precisely because two branches' independent edits to them aren't safe to merge by
hand either (see the mechanical `frontend/package-lock.json` conflict this same rebase hit).
Generating fresh in CI, immediately before the type-check/build step that consumes it, means
there is never a second copy to drift from — the "staleness" failure mode 004 was correctly
worried about (frontend silently type-checking against routes that no longer exist) is
structurally impossible once nothing is committed, not caught after the fact by a diff.

**Alternatives considered**:
- *Keep 004's committed copy, regenerate it as part of this fix, and add a CI step that
  regenerates-and-diffs to catch drift.* This is the brief's own suggested fallback, and was
  seriously considered. Rejected in favor of not committing at all: a diff-based drift check
  only ever fires *after* someone already forgot to regenerate and committed the stale file —
  it catches the mistake one CI run late, whereas generating fresh removes the mistake's
  precondition (there is no committed file to forget to update).
- *Commit `openapi.json` (the OpenAPI document itself) instead of the generated `.d.ts`,
  generating types from that file at build time.* A legitimate alternative the brief itself
  named — makes the frontend build hermetic (no live backend needed, just a static JSON file)
  at the cost of a second generation step (`export /openapi.json` from the backend, then
  `openapi-typescript` from the file) and a new place for the same staleness problem to hide
  (the committed `openapi.json` itself can drift from the backend's actual routes, just one
  layer further removed from the symptom). Rejected because it trades one committed artifact
  for another without removing the underlying risk, and this repo already has a working
  pattern for "needs a live backend in CI" (the backend job's own `supabase start` +
  `supabase db reset`) — starting `uvicorn` for a few seconds to serve `/openapi.json` is a
  smaller addition than it looks.
- *Run `npm run generate:api-types` in a local pre-commit/pre-push git hook instead of CI.*
  Rejected — hooks are opt-in per developer machine and silently do nothing if not installed;
  a CI-enforced step is the only one that can't be skipped by forgetting to set something up
  locally.

---

## 21. Calendar event window and freshness — two deferred gaps

Both surfaced from using the working feature, not from reading the spec. Neither
blocks anything; both are recorded here rather than fixed now.

### 21.1 The 7-day / 20-event window feels short

`google_calendar.py` sets `EVENT_WINDOW_DAYS = 7` and `EVENT_MAX_RESULTS = 20`, per a
recorded clarification in `specs/012-calendar/spec.md`: *"Next 7 days, capped at 20 events.
Matches the design's plain scrollable list with no pagination control."*

**This is not an arbitrary number — it is anchored in the design's own copy.**
`calendar.empty.body` reads *"Nothing on your calendar **this week**."* A wider window
would make the empty state contradict what the list actually shows.

**If it is widened**, three things move together, and skipping any one leaves an
inconsistency:

1. `EVENT_WINDOW_DAYS` and probably `EVENT_MAX_RESULTS`.
2. `calendar.empty.body` — "this week" stops being true.
3. The design system's *"plain scrollable list, no pagination"* decision — 20 events is
   already a long scroll on a phone; 50 is a different screen and would need a
   "load more" affordance the design does not contain.

So this is a **design change**, not a constant tweak. **Status: deferred.**

### 21.2 Every visit to `/calendar` hits Google live

There is no caching anywhere in the calendar path. `get_valid_access_token` is efficient —
it refreshes only when the stored token has actually expired, so a page load makes exactly
one Google call. The latency is the network round-trip itself, which on a slow connection
has been observed at ~10s (the OAuth token exchange took 11.1s on the same link).

The design system says nothing about calendar caching, so there is no specified behaviour
to implement — this is a genuine gap, not an unimplemented requirement.

Options, if it is picked up:

| Option | Effect | Cost |
|---|---|---|
| **Short-TTL per-user cache (~5 min)** | Second and later visits instant | Events added in the last 5 minutes do not appear |
| Cache + manual refresh control | Instant, with a way to force a fetch | Adds a control the design system does not specify |
| Optimistic render, refresh in background | Feels instant | Needs a staleness indicator; more moving parts |

**Recommended when picked up: the short-TTL cache.** Smallest change, adds no unspecified
UI, and five-minute-stale data is acceptable for "pick an event to style for." There is
precedent in the salvaged pipeline — feature 005's per-user suggestion cache solves the
same problem the same way.

**Status: deferred.** Correct today, just slow on a slow link.

---

## 22. Feature 005 (Closet write) — two gaps the handoff asked to be decided here

### 22.1 Wear history shape, and same-day double-tap semantics

The handoff (`docs/handoffs/005-closet-write.md` §5.1, §2.3) named this as a modelling decision,
not a column choice, and asked for the "tapped twice in one day" question to be resolved
explicitly rather than assumed.

**Decision: an `item_wears` table, one row per item per calendar day (unique on
`(item_id, worn_date)`), not one row per tap.**

A `worn_count` integer was rejected first and for the reason the handoff already gives: it
can't answer "most worn this month" (Outfits' specified sort) and can't be undone. That leaves
the real question — does a table record one row per *tap* or one row per item per *day*?

**One row per day.** "Log as worn today" reads as a same-day boolean claim about the garment
("I wore this today"), not an event counter the user is aware they're incrementing. The design
gives this action no confirmation step and no on-page feedback (§2.3: Item detail shows no worn
indicator at all) — so a user has no way to notice a second tap even happened. If a second tap
inserted a second row, an accidental double-tap (fat finger, an impatient repeat-tap while a
request is in flight, a retried network request) would silently inflate that item's future
"most worn" ranking with nothing on screen to catch it. A per-day-unique row makes the action
naturally idempotent: the second tap the same day is a harmless no-op against the existing row,
matching what the button's own label already promises and nothing more.

Implementation: `item_wears(id, item_id, user_id, worn_date date not null default current_date,
created_at timestamptz not null default now())`, unique constraint on `(item_id, worn_date)`.
The route issues an upsert (`ON CONFLICT (item_id, worn_date) DO NOTHING`) so a repeat tap the
same day returns success without a second row or a client-visible error — consistent with there
being nothing on the page to show a difference between "just logged" and "already logged today"
either way.

**Alternatives considered:**
- *One row per tap, no uniqueness constraint.* Rejected — this is what the handoff already
  flags as the option that answers "most worn" and supports undo, so it isn't obviously wrong;
  it was rejected specifically because it's the option most exposed to the accidental-double-tap
  failure mode above, and nothing in the design gives the user a way to see or correct an
  inflated count. If a future feature wants true multi-wear-per-day tracking (rare for
  clothing — the closest real case is a swim then change scenario), it can relax the unique
  constraint then, with a reason attached to that feature's own decision record; loosening a
  constraint later is cheap, and recovering historical per-tap data after the fact is not.
- *A `last_worn_at` timestamp column on `wardrobe_items` instead of a separate table.* Rejected
  for the same reason `worn_count` was: it answers "when was this last worn" but not "most worn
  this month" (Outfits' sort needs a count over a window, not a single latest timestamp), and a
  single mutable column can't be an audit trail.

### 22.2 Delete confirmation

The handoff (§5.4) flags this as a real gap: the design specifies no confirmation before the
overflow menu's `danger`-tone Delete row fires, and asks for a decision plus alternatives to be
recorded rather than silently picking either way.

**Decision: add a confirmation step.** A single tap in a four-row menu triggering an
unrecoverable hard delete of a garment the user photographed themselves is a harsh outcome for
one mis-tap, and the four rows (Edit, Log as worn today, Favorite, Delete) sit close enough
together in the same sheet that a fast or imprecise tap choosing the wrong one is a realistic
failure mode, not a hypothetical one. The cost side of this trade is small — one extra
deliberate tap — against a cost on the other side that cannot be undone at all.

Implementation follows the same escape hatch design-system.md §3 and this document's §18
(calendar permission primer) already use and name explicitly: *"Bespoke variants not on this
component... richer than BottomSheet's plain label rows."* A small bespoke confirmation card,
real `<dialog>` modal semantics (`showModal()`, focus trap/restore, safe-area-aware bottom
padding — matching BottomSheet's own treatment), title "Delete {item name}?", body "This can't
be undone.", a secondary "Cancel" and a danger-toned "Delete" action. This is content shown in
response to a destructive action, not a new form control, so it isn't the kind of invented
component §VIII warns against — it's the same pattern already used once in this codebase for
exactly this situation (an irreversible or consequential action needing more explanation than a
BottomSheet row can hold).

**Alternatives considered:**
- *No confirmation, matching the design literally.* Rejected — the handoff itself calls this
  gap out as real rather than asking it to be silently accepted, and the danger-tone treatment
  on the row is itself evidence the design already recognizes this action needs to read as
  risky; a risky-looking action with no actual friction before it fires is the worst of both
  options; it *looks* dangerous without *behaving* carefully.
- *Soft delete with an "Undo" toast instead of a blocking confirmation.* Considered
  seriously — it's the more modern pattern and avoids an extra tap on the common path. Rejected
  because the handoff's own scope table (§5.2) states plainly "Delete — Hard delete", and a
  `deleted_at` column plus a restore path is materially more schema and route surface than
  either the handoff or this feature's spec describes; that trade belongs to a future feature
  making it deliberately, not to this gap-fill inventing it as a side effect.
- *Browser-native `confirm()`.* Rejected — untestable in the design system's terms (no tokens,
  no control over copy or button styling, inconsistent across browsers), and the codebase
  already has a documented bespoke-dialog pattern (§18) that does the same job with the design
  system's own visual language.

---

## 23. Feature 006 (Photo upload + vision) — six named gaps plus two `known-gaps.md` items

Full reasoning and rejected alternatives for every entry below live in
`specs/006-photo-upload-vision/research.md` (the same split feature 012 used for §16) — this
section exists so each decision is discoverable from the same document every other cross-cutting
choice lives in, not to duplicate the argument.

### 23.1 Storage bucket privacy and signed URLs

**Decision**: private bucket (`wardrobe-photos`), declared in `infra/supabase/config.toml`, not
created by hand in Studio. The backend mints a 1-hour signed URL at read time
(`GET /closet/items`, `GET /closet/items/{item_id}`), returned as a new `photo_url` field —
nothing signed is ever stored. A public bucket was rejected: these are photos of a person's
clothes in their home, the same privacy class `wardrobe_items` itself already gets RLS
protection for, and a public bucket has no revocation story if a path ever leaks. Full
reasoning: `research.md` §2.

### 23.2 Maximum upload file size

**Decision**: 10 MiB, enforced in the extract route before the file is read or forwarded, and
mirrored as the bucket's own `file_size_limit` in `config.toml` as a second backstop. Full
reasoning: `research.md` §3.

### 23.3 Review-card / required-attribute mismatch

**Decision**: `CreateWardrobeItemFromUploadRequest` relaxes Formality, Warmth, Season, Fabric,
Pattern and Fit from required to optional, matching `WardrobeItemPatch`'s existing shape. The
three columns that are `NOT NULL` in the database (Formality, Warmth, Season) get a documented,
conservative default when neither the scan nor the user supplied a value (`"casual"` / `3` /
all four seasons); Fabric, Pattern and Fit are simply stored `NULL`, since the database already
allows it. Nothing blocks a save. The alternative of extending the review card itself was
rejected as a direct Principle VIII violation; the alternative of blocking save on any missing
field was rejected as reproducing the exact "extraction failure must be a 200" problem the
handoff calls out. Full reasoning and a fourth option (migrating the columns to nullable
instead) considered and rejected: `research.md` §4.

### 23.4 Color text field writing into a hex column

**Decision**: the review card's Color field pre-fills with the derived name of the scanned hex
(`colors.nearest_names`, the same function `ItemEditForm`'s own Colour field already uses). On
save, the text is matched case-insensitively against `FASHION_COLOR_PALETTE`'s exact keys
(`colors.name_to_hex`, unchanged); an unmatched value is rejected with a clear message rather
than silently approximated. A swatch-picker was rejected as contradicting the design's stated
"Color (text)" field; a fuzzy "nearest string" match was rejected because it can silently store
a materially wrong color with nothing telling the user a substitution happened. Full reasoning:
`research.md` §5.

### 23.5 Partial bulk-save failure

**Decision**: per-card isolation. A failed card shows `Button`'s existing Error treatment
("Try again") in place; cards already saved before it are unaffected and the queue does not
silently skip or auto-advance past the failure. Aborting/rolling back the whole batch was
rejected (it would delete a user's already-successful saves to "fix" an unrelated item);
silently skipping was rejected as the literal failure mode this decision exists to prevent. Full
reasoning, plus a fourth "explicit skip affordance" option considered and deferred: `research.md`
§6.

### 23.6 Camera permission primer — copy

**Decision**: follows design-decisions §18's established bespoke-`<dialog>` shape exactly.

| Element | Copy |
|---|---|
| Title | Before you scan |
| Body | I'll use your camera to scan the garment so I can fill in its details automatically. Nothing is saved until you review and confirm. |
| Primary action | Continue |
| Secondary action | Not now |

Full reasoning, including why "Continue" (not "Continue to Camera") was chosen: `research.md`
§7.

### 23.7 Review progress bar — animates

**Decision**: the "Reviewing item X of Y" progress bar transitions with the existing
`--motion-duration-base`/`--motion-easing-standard` token pairing, gated by
`prefers-reduced-motion` (falls back to an instant jump). From `design-system.md`'s own Open
Questions list, folded into this feature's scope per the handoff §10. Full reasoning:
`research.md` §8.

### 23.8 "Enter manually" — same review form, blank

**Decision**: the "no garment found" empty state's "Enter manually" action advances to the
identical six-field review card already built for the scanned case, every field blank, the same
uploaded photo still attached. No second, purpose-built manual-entry form is built — doing so
would contradict the handoff's own "every form control already exists, do not build new ones."
Also from `design-system.md`'s Open Questions list. Full reasoning: `research.md` §8.

---

## 24. Feature 008 (Styling chat) — item resolution

**Decision**: outfit items are resolved to full closet items (name, category, signed
`photo_url`, etc.) **server-side**, inside the same request that already calls the pipeline —
reusing `closet.py`'s existing `ClosetItemView.from_wardrobe_item` + one batched
`storage.create_signed_urls` call, the identical pattern `GET /closet/items` already uses for a
page of items. Rejected: the client fetching each item individually after the reply arrives (N
sequential round trips stacked after an already multi-second pipeline call — exactly the
"works but takes a fortune" experience the handoff calls out); a new batch
get-items-by-ids endpoint (solves the round-trip count but not the added-latency problem, and
duplicates logic the styling route can already do inline with data it has in hand). Full
reasoning: `specs/008-styling-chat/research.md` §1.

## 25. Feature 008 (Styling chat) — thread identity

**Decision**: `thread_id` is owned by the server — the pipeline's own existing `uuid.uuid4()`
fallback (unmodified, Principle I) mints it when a request omits one, and the route always
echoes it back. The client never invents an id and never persists one beyond the mounted
conversation (no `localStorage`/`sessionStorage` in this slice); "New chat" simply drops the
held value so the next send gets a fresh server-minted id. Consequence, stated explicitly since
011 builds chat history on top of this: a full page reload starts a new *visible* conversation
client-side even though the old thread's checkpointed state may still exist in Postgres — 011's
"Continue" flow is what closes this gap by persisting session metadata (including its
`thread_id`) somewhere durable, which is out of scope here. Rejected: client-generated UUIDs
(duplicates identity-minting logic the pipeline already owns, and lets a client pick an
arbitrary/guessable id with no benefit); one eternal thread per user (conflicts with both "New
chat" and 011 needing genuinely distinct, independently listable conversations). Full reasoning,
including the bounded cross-thread risk this leaves unaddressed and why: `specs/008-styling-chat/
research.md` §2.

## 26. Feature 008 (Styling chat) — request shape and latency

**Decision**: plain synchronous request/response (one `POST`, one JSON reply) — the same shape
every other route in this codebase already uses — with **no user-experience-driven wait cap**
and a **120-second backstop timeout** at the request layer so a genuinely stuck request still
surfaces a retryable error instead of hanging forever. This overrides the handoff's own
suggestion to "set a real timeout" in the tighter sense: asked directly, the repo owner chose "no
fixed cap, but a generous backstop" over any specific shorter number (`specs/008-styling-chat/
spec.md` Clarifications, 2026-08-01). Rejected: streaming (the pipeline's only real entry point
is `graph.invoke()`, used unmodified by every existing caller including the eval harness;
switching to `.stream()` is new, unevaluated invocation behavior forbidden without an eval
re-run, and the generation node's LLM call isn't incremental anyway); async job + polling (no
job-queue concept exists anywhere in this codebase, and introducing one contradicts the Quality
Bar's simplicity rule once the motivating problem — a long blocking wait — is exactly what the
repo owner said doesn't need solving). Full reasoning: `specs/008-styling-chat/research.md` §3.

## 27. Feature 008 (Styling chat) — the checkpointer's self-created tables

**Decision**: accept `PostgresSaver.setup()` as the bootstrap mechanism (documented, not
silent), and make it run once, deterministically, at backend process startup — `main.py`'s
existing `lifespan` context manager already eagerly constructs the DB engine at startup rather
than at first request for exactly this reason; this feature adds one more line to that same
function to warm `pipeline.graph.get_compiled_graph(...)`, which creates the checkpoint tables as
a side effect before any request is served. No migration `0007` is added. Rejected:
hand-authoring a migration that pins `PostgresSaver`'s internal schema (that schema is
LangGraph's to change; a checked-in copy can silently drift the moment LangGraph changes it
internally, without the migration file itself changing — the same two-sources-of-truth failure
the constitution's Alembic-vs-Supabase rationale already warns about, aimed at a library's
internals instead of a second migration tool); doing nothing / fully lazy on first request (works,
but pays the one-time DDL cost inside whatever the first real user's request happens to be, and
risks a multi-worker race under concurrent test setups — both avoidable for one line at startup).
Full reasoning: `specs/008-styling-chat/research.md` §4.

## 28. Feature 008 (Styling chat) — what the composer's send actually does, vs. "Start styling"

Not one of the handoff's four named decisions, but a real gap the anatomy spec surfaces without
resolving: design-system.md's Recommend anatomy lists **both** a pinned composer with its own
28px send button (item 6) **and** a full-width "Start styling" button that "appears once the
user has sent a message," captioned "Uses everything you have told me so far" (item 5) — two
distinct controls, and the spec never states what each one actually triggers against a real
backend. The reference prototype's own (unshipped) simulation code resolves the ambiguity
unambiguously: `sendMessage()` only ever appends to local chat state and returns a canned,
non-AI acknowledgement; `startStyling()` is the one path that joins the accumulated user text and
runs the (simulated) generation (`design/prototype/What to Wear.dc.html:1834-1861`).

**Decision**: the composer's send is **local-only** — it appends the user's message to the
on-screen transcript and does not call the backend. "Start styling" is the **sole** trigger for
`POST /recommend/messages`; it sends everything typed since the *last* Start-styling call (on the
first tap, that is every message so far, which is exactly what "uses everything you have told me
so far" describes) as `message`, with the held `thread_id` (§25) carrying continuity so the
pipeline's own refinement parsing (unmodified, `_parse_refinement_intent`) treats a later tap's
batch as a refinement utterance rather than a fresh, unrelated request. The button is visible once
the conversation has at least one user message, and disabled specifically when there is nothing
new pending since the last tap (avoids a no-op duplicate call, not specified either way by the
design system but a reasonable implementation-level safeguard). No intermediate assistant
"acknowledgement" bubble is built — the prototype's keyword-sniffed canned acknowledgements
("Got it, a rainy day commute...") are demo flavor, not text in design-system.md's own copy
tables (§6), so inventing and shipping them would violate Principle VIII's "nothing visual is
invented in code" the other direction (inventing unspecified copy, not omitting specified copy).
The composer's own "Thinking…" row and input/send disabling (design-system.md "Chat input
behavior") apply while a Start-styling call is in flight, not on ordinary composer sends, which
are instant and local.

**Rejected**: (a) every composer send calling the real pipeline immediately, dropping "Start
styling" as prototype-only flourish — directly contradicts design-system.md's explicit,
verbatim-required anatomy item 5 and its copy, and produces a full retrieval+LLM call on every
single message with no user control over when the expensive call fires, worsening exactly the
latency/cost concern the handoff raises. (b) routing the composer's send through a real, trivial
backend endpoint that returns a canned acknowledgement — adds a network round trip and a new
endpoint for text that is discarded, ephemeral, and has no reason to be server-authoritative;
Quality Bar's simplicity rule counsels against server surface with no measured need. Full
reasoning: `specs/008-styling-chat/research.md` §7.

## 29. Feature 008 (Styling chat) — where the greeting's `{name}` comes from

design-system.md's Recommend hero state twice specifies the greeting as literal `"{greeting},
{name}"` copy, but no `{name}` source exists anywhere in the app: Settings' Account section
(design-system.md §4's Settings table) has only an email field, sign-up collects only
email/password, and no display-name field appears anywhere in the design system's Settings spec
or `known-gaps.md`.

**Decision**: derive `{name}` from the signed-in user's email local-part (the part before `@`,
already read client-side via `supabase.auth.getSession()` — the same call `app/(app)/profile/
page.tsx` already makes for the same purpose), title-cased on `.`/`_`/`-`/`+` separators
("jane.doe@x.com" → "Jane Doe"; "maya@x.com" → "Maya"). Rejected: adding a new display-name
field to Settings/the profile schema — invents a field the design system never specifies
anywhere (a Principle VIII violation the other direction, same shape as §28's rejected option),
and is unrequested scope for this slice. Rejected: dropping `{name}` from the greeting entirely
— contradicts the literal, twice-stated copy pattern.

---

*Every item above is decided except those explicitly marked **deferred** (§21), which are recorded gaps awaiting a decision rather than open questions blocking work.*

## 30. Feature 006 — the review card carries every extracted attribute

**Status: decided.** Reverses §23.3 and amends §23.4.

### The defect this fixes

`vision.py` extracts eight attributes: `category, colors, fabric, warmth,
formality, season, pattern, fit`. §23.3 decided that the design system's
six-field Add-item review card (Name, Category, Group, Fabric, Color, Notes)
should not be blocked by anything outside it, and relaxed
`CreateWardrobeItemFromUploadRequest` accordingly. The frontend then never sent
the other five, and the write path substituted constants for the three that are
`NOT NULL`.

Measured on real uploads: four photos of visibly different garments all stored
`formality='casual'`, `warmth=3`, `season=[spring,summer,autumn,winter]`,
`pattern=NULL`, `fit=NULL`. That is not a conservative default, it is fabricated
data — indistinguishable from a real reading, and fed straight into a styling
pipeline whose scorers reason over exactly these fields (`formality_coherence`,
`weather_fitness`). The scan appeared to work while contributing nothing.

§23.4 compounded it for colour: the card displayed a derived NAME and sent that
name back, so `hex → nearest name → palette hex` replaced the detected value
(`#22345d` stored as navy's `#1b2a4a`), and a multi-colour garment collapsed to
one entry.

### The decision

The review card carries **all eight** extracted attributes, plus Name, Group and
Notes. `formality`/`warmth`/`season` are required by the request model; the write
path never defaults. Colour is a `TagInput` of hex values displayed by name — an
untouched chip is sent as its original detected hex, and anything typed is sent
as typed for the backend to resolve.

This is a **deliberate deviation from design-system.md's Add-item field table**,
which lists six fields. The table describes what a person edits, and was written
against a prototype with no real extraction behind it; it cannot reasonably be
read as an instruction to discard three quarters of what the scan produces. The
legacy app's own `ExtractedItemForm` carried all eight and enforced "100% of
saved items populated, none blank" (its SC-003) — this restores that guarantee.

### Options considered

| Option | Rejected because |
|---|---|
| Keep six fields, pass the other five through invisibly | Preserves the data, but a user cannot see or correct a wrong `formality` before it reaches the styling pipeline — and a wrong one is worse than a missing one, because nothing downstream can tell. Also leaves the scan's actual findings unauditable, which is how the original defect stayed invisible for two features. |
| Keep six fields, show the other five read-only | Same visibility gain, but a wrong value then has no in-flow correction — the user must save a known-wrong item and edit it afterwards. |
| Keep §23.3, make the three columns nullable instead | Removes the fabrication but not the loss: the pipeline would then reason over NULLs for every scanned item. The extractor already produces these values; the fix is to stop dropping them, not to make dropping them representable. |
| **All eight, editable (chosen)** | — |

### Consequences

- Save is blocked when Category, Formality, Warmth or Season is empty
  (`add_item.incomplete`). The scan fills these in nearly every case, so this
  surfaces only on a genuine extraction failure — where the legacy behaved the
  same way.
- **Every taxonomy field on this card is a chip group** — Category, Formality,
  Warmth and Season alike. `Select` was tried for Formality and Warmth and
  rejected: a native dropdown hides every option behind a tap and an OS sheet
  on a phone, for two fields the scan usually pre-answers and the user is only
  verifying. It also carried a hazard of its own — a `<select>` whose value
  matches no option silently selects its FIRST, so an undetected formality
  displayed, and would have saved, as "casual". A chip group shows nothing
  selected, which is the truth.
- **Colour is hex, and is shown as colour.** A swatch (`<input type="color">`,
  which gives a real OS picker on both mobile platforms and cannot produce a
  non-hex value) beside the literal `#rrggbb`, with add/remove per entry —
  the same control the legacy app used. An intermediate version displayed the
  derived NAME instead: that both destroyed the detected value on the round
  trip and told the user nothing, since "navy" does not say which navy the
  scan read. Names are still derived for display elsewhere (`color_names` on
  the closet item), just never as the editable representation.
- `fabric`/`pattern`/`fit` stay optional: the column is nullable, so an honest
  "not detected" is representable without inventing anything.

## 31. Feature 006 — colour swatches, Category vs Type, and 1:1 photos

**Status: decided.** Amends §30.

### 31.1 Colour is hex, and hex is never shown

The review card renders a row of **swatches** (`<input type="color">`), each with
a remove control, plus an add button. The value is `#rrggbb` throughout; the code
itself is not displayed.

Three versions, two wrong:

| Version | Problem |
|---|---|
| Name in a text field | Sent the NAME, so the detected value round-tripped through the palette: `#22345d` stored as navy's `#1b2a4a`, and multi-colour garments collapsed to one entry (§30). |
| Swatch + `#rrggbb` text | Data correct, but printed a machine code where a colour belongs. The swatch already answers "which colour" exactly and instantly. |
| **Swatch only (chosen)** | — |

The native colour input is deliberate: a real OS picker on both mobile platforms
for free, and it cannot emit a non-hex value — so with the text field gone, a
malformed colour is unreachable through the UI. The hex validation behind it
remains as a guard on values arriving from the scan.

### 31.2 Category and Type are different fields

They were one state variable, so choosing "Top" overwrote a detected `blouse`
with the bare group name — which is why every scanned item stored a group name
rather than a garment type.

- **Category** — the fixed five chips (Top, Bottom, Outerwear, Footwear,
  Accessory; `full_body` files under Bottom, as feature 004 already resolved for
  the Closet filter). Not stored: `categories.group_of` derives it.
- **Type** — the specific garment *within* that category (an accessory is a tie,
  a bow tie, a necklace, a ring). This is what `wardrobe_items.category` holds.
  Choosing a Category narrows which Types are offered; re-choosing the Category a
  Type already belongs to keeps it.

`CATEGORY_GROUPS` gained the specifics this made necessary (shirt, hoodie,
bow_tie, necklace, ring, earrings, bracelet, ankle_boots, …) — exactly what
`categories.py`'s docstring invites, and Principle VI freezes the six *group*
names, not the category list.

The vocabulary is served by `GET /api/v1/taxonomy/categories` rather than
mirrored in TypeScript. The colour palette is already hand-mirrored with a "keep
in sync" comment; this table changes far more often, and a second hand-copy would
drift (Principle VII). A failed fetch leaves Type unselectable but never blocks a
save — `category` is a free string on the backend.

The vision prompt (v2) now asks for the specific type from the known vocabulary,
so `group_of` always resolves rather than falling through to its
`accessory` default.

### 31.3 Photos are 1:1, letterboxed in their own background colour

Every item photo renders square — closet tile, item-detail hero, styling-reply
thumbnail — via one `ItemPhoto` component. Garment photos arrive in wildly
different ratios and a grid of mixed shapes reads as broken.

`object-fit: contain`, never `cover`: a crop silently amputates sleeves and
shoes, which is worse than a band of colour. That band is why the VLM now also
returns **`background_color`** — the dominant colour of the photo's *backdrop* —
stored as `wardrobe_items.photo_background_color` (migration `0008`). The padding
then continues the photo instead of interrupting it.

Kept out of `colors` deliberately: that column is the garment's colours and feeds
the colour-harmony scorer, which would otherwise score the wall the user
photographed against. It is a presentation attribute of the photo, never surfaced
as an attribute of the item.

The vision golden set compares `category` at **group** level rather than by
exact string, since the prompt now asks for a specific type: a correct
`t-shirt` would otherwise fail a case expecting `top`. `categories.group_of` is
the same mapping the app uses to slot an item, which is what those cases are
really asserting.

Nullable, with `--color-surface-sunken` as the fallback — the VLM leaves it null
on a busy backdrop, and every item added before `0008` has none. There is no
correct value to invent, and the app's own surface is the right answer when
there is nothing better.

**Threading it is the part that broke.** The field was added to the extractor,
the request model and the database, and then for one commit not passed from the
extract response into the save body at all — so every item added through the UI
stored `null`, and every non-square photo letterboxed in the app's surface colour
rather than its own backdrop. The same defect §30 records for the other five
attributes, repeated within two commits of fixing it. `buildFromUploadBody` now
takes it as a parameter, so the single and bulk flows cannot drop it
independently, and both suites assert it reaches the request.

Verified against the live VLM with a 600×900 photo of a dark red block on a sand
backdrop: it returned `background_color: #d9c9a1` against a true `#d9c9a8`, and
`colors: ["#7f1d2d"]` against a true `#7a1f2b` — genuinely separated, neither
leaking into the other.

**Deviation from design-system.md § Image treatment**, which specifies fixed
heights (120px tile, 220px hero). Those were written against a prototype whose
"photos" were all the same placeholder rectangle, so the question of real,
varying aspect ratios never arose.

## 32. Feature 009 (Suggestion pager) — outfit persistence: schema and the favorite/save mechanic

**Status: decided.**

### The gap (handoff §3)

No table anywhere in `infra/supabase/migrations/` persists an outfit. The pager's favorite heart
and its card-tap-through (`design-system.md` § Outfit suggestion pager, item 1 and the closing
paragraph) both need a saved outfit with an id to act on. The handoff names three options and
recommends the first; this section adopts that recommendation and records the schema built on
top of it, since the handoff explicitly asked for the schema shape and the favorite mechanic to
be decided here, not guessed.

### Decision: 009 owns persistence, 010 owns the browsing screens

Adopted as the handoff frames it. Rejected alternatives (restated from the handoff, with why):

| Option | Rejected because |
|---|---|
| Defer the heart and tap-through to 010 | Ships every card missing two design-specified elements, and 010 then has to revisit a screen it doesn't own to add them. |
| Heart with component-local state only | Forgets on reload — indistinguishable from a broken feature to the user, and contradicts the design system's explicit tie to the gallery's shared favorite state. |
| Build 010 (gallery) first | The gallery has nothing to list until an outfit can be saved — inherits the identical ordering problem, just pointed the other way. |

### Schema — `outfits` table, minimal

```sql
create table outfits (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  occasion text not null,
  meta_line text not null,
  rationale_text text not null,
  match_label text not null check (match_label in ('great', 'good', 'might_work')),
  item_ids uuid[] not null,
  favorite boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

Follows `0002`'s RLS-and-GRANT pattern exactly (`for all using (auth.uid() = user_id) with
check (...)`, plus the table-level `grant select, insert, update, delete ... to authenticated`
`0002`'s own comment documents as non-optional), proven by a two-user isolation test the same
shape as `004`'s.

**What's in, and why each field earns its place** ("what it costs to save and re-read a
suggestion," per the handoff):

- `item_ids uuid[]` — not a join table. A join table (`outfit_items(outfit_id, wardrobe_item_id,
  position)`) is the more extensible shape 010 might eventually want (per-row metadata, easier
  referential integrity), but nothing in this slice reads or writes per-item metadata — it would
  be schema for a need that doesn't exist yet, which the Quality Bar's simplicity rule counsels
  against. Order is preserved by array position, which is all the pager needs. **Rejected**: a
  join table now (no measured need this slice has); a single `jsonb` blob of resolved item views
  (photo URLs, names) captured at save time (stale the moment the source item's photo or name
  changes — re-resolving live from `wardrobe_items` by id, the same pattern `_resolve_outfit`
  already uses, is one query and stays correct).
- `rationale_text`, `match_label` — exactly what the card displayed; re-deriving `match_label`
  from a stored score would require storing the score too, which is the one thing § Scores
  forbids persisting as a renderable value outside this table's own internal bookkeeping. Storing
  the label directly (not the float) keeps the "never render a number" guarantee true even for
  data at rest, not just data in transit.
- `occasion`, `meta_line` — not obviously required by "save and re-read," but cheap to capture
  now and otherwise **unrecoverable** later: the meta line is derived from the request-level
  `Context` (§34 below), which this feature does not persist anywhere else. Omitting these two
  fields would mean a saved outfit could never show its own meta line again once 010 builds a
  screen for it — an honest gap that costs two text columns to avoid now versus a schema
  migration later. **Rejected**: storing raw `Context` (formality/condition/temp_band) and
  re-deriving the line at read time — more fields, more coupling to `Context`'s own shape, for a
  string this feature already computes once and can freeze.
- No `thread_id` — nothing in scope reads a saved outfit back by conversation, and 011 (chat
  history) is a separate, later persistence story for threads themselves; adding it now would be
  speculative.

### The favorite/save mechanic: one boolean, toggled — not insert/delete

**Decision**: the heart's first tap **inserts** a row with `favorite = true` (the row's mere
existence *is* "saved" — there is no "saved but not yet decided" intermediate state in this
slice, since nothing else can create the row). The heart's second tap **flips** `favorite` via
the same `UPDATE ... SET favorite = NOT favorite ... RETURNING favorite` pattern
`toggle_favorite` already uses for `wardrobe_items` (`repositories/supabase_closet.py`) — it does
**not** delete the row.

**Rejected**: delete the row on the second tap. This reads as simpler at first (unsave = gone,
matching "the heart is the only way in"), but it conflates two actions design-system.md keeps
separate on the Outfits gallery card: the direct heart (favorite/unfavorite) and the overflow
`BottomSheet`'s own Delete row (§ Screen anatomy → Outfits, item 2's overflow menu, mirroring
Item detail's Favorite/"Log as worn"/Edit/Delete split). If unfavoriting deletes, 010 can never
offer a "saved but unfavorited" outfit — a real, useful state design already reserves an
overflow-menu Delete action to control instead. Toggling a flag costs nothing extra now and
avoids painting 010 into a corner. This mirrors the wardrobe item favorite convention already in
the codebase rather than inventing a second one.

## 33. Feature 009 (Suggestion pager) — the pager card carries no citations, contradicting one line of screen anatomy

**Status: decided.** design-system.md contradicts itself, and `docs/design-decisions.md` is
the resolution mechanism CLAUDE.md and Constitution VIII specify for exactly this case.

### The contradiction

§ Badge is unambiguous: the `citation` tone is *"used **only in Outfit detail's description**,
never in the chat outfit card — the chat card's description is plain text with no citation
markers."* § Outfit suggestion pager (the dedicated component spec) repeats this for the pager
specifically: *"Description: the styling explanation as plain text directly on the card — no
nested tinted surface, no inline citation Badges (Citations are detail-page-only, see § Badge)."*
Both are detailed, deliberate, and reference each other.

Screen anatomy → Recommend, item 3's closing sentence describes the pager differently: *"a
swipeable card per suggestion, each with its own header ..., **its own citation-bearing
reasoning block and rule list**, its own thumbnail row, and its own thumbs-up/down feedback
footer."*

### Resolution

The two component-level sections (§ Badge, § Outfit suggestion pager) win. The anatomy
sentence is read as an artifact of 008's single-outfit citation pattern (bubble text + inline
`[n]` badges + rule list, which the anatomy paragraph describes correctly for the *non-pager*
case one sentence earlier) that was never fully rewritten when the pager's own, later, far more
detailed component section was added — it is describing the pager by analogy to the single-
outfit case immediately above it, not stating an independent requirement. Weighing which
passage to trust: § Badge is the section whose entire purpose is pinning down exactly where the
`citation` tone may and may not appear, stated twice, both times naming the pager card by
exclusion. A one-clause aside in a screen-anatomy paragraph that is otherwise a high-level tour
is the weaker source when the two conflict — this is the same reasoning `docs/design-
decisions.md` has applied to every prior contradiction in this document, not a new rule invented
for this feature.

**Consequence**: a pager card's description is plain text, full stop. No `[n]` markers, no
`Badge`, no rule list on the card. Citations remain reachable only via the assistant bubble's
existing single-outfit rendering path (unchanged, still used whenever a reply resolves to
exactly one outfit total pre-pager — see §35) and, later, Outfit detail (010).

## 34. Feature 009 (Suggestion pager) — the meta line's `{occasion} · {formality|weather}`

**Status: decided.**

### The gap

§ Outfit suggestion pager item 4 specifies a meta line reading `{occasion} · {formality|
weather}` per card, but neither `ScoredOutfit` nor `StylingOutfit` carries an occasion or a
formality/weather field — those exist only on the pipeline's request-level `Context`
(`schema.py`), which today isn't threaded into any response the frontend sees at all.

### Decision

Both halves of the meta line are read from `SuggestResult.context` — **once per reply, shared
across every card in that reply's pager**, not derived per-outfit — because a `Context` is the
pipeline's own understanding of the single request that produced every outfit in the reply; there
is exactly one per reply, never one per outfit.

- `{occasion}` = `context.occasion` (the pipeline's own normalized occasion text, not necessarily
  identical to the raw composer text — it's already been through `parse_request`).
- `{formality|weather}` = `context.condition` (e.g. "rain") when the pipeline detected one,
  **falling back to** `context.formality`'s label when it did not. Weather is preferred when
  present because it is the more specific, opt-in signal (only set when the request actually
  implied weather); `formality` is always present (`Context.formality` is a required field) so it
  is the correct fallback rather than an empty slot.

**Rejected**: showing both formality and weather concatenated — the design's literal `{formality
|weather}` token uses a pipe, read here as "one or the other," not "both"; showing both would
also make an already-terse 10.5px line noticeably longer on every card for marginal gain.
**Rejected**: computing formality from the resolved items' own `formality` fields (e.g. the
modal value across the outfit's garments) instead of `context.formality` — this would silently
diverge from what the user actually asked for (a request for "business casual" could return
items whose stored formality reads slightly differently than the requested band) and would be
new per-outfit computation the pipeline doesn't do today, which Principle I counsels against
introducing in a route that has no reason to re-derive something the pipeline already decided.

## 35. Feature 009 (Suggestion pager) — response shape: `outfits[]` replaces `outfit`, and where the single-outfit path goes

**Status: decided.**

`SendMessageResponse.outfit: StylingOutfit | None` becomes `outfits: list[StylingOutfit]`
(never null — an empty list is the "nothing surfaced" case, matching § Outfit suggestion pager's
own Empty group-state rather than a separate null branch). Every reply that resolves to one or
more outfits now renders through the pager unconditionally, including the single-outfit case
(FR-003: one card, no arrows/indicator) — the handoff's mission is explicit that this
"replac[es] 008's single flat item-thumbnail-row rendering entirely," so there is no remaining
surface, at any outfit count, that renders the old bubble-plus-inline-citations treatment.

Consequently `SendMessageResponse.citations: list[CitedRule]` and the `[n]`-marker embedding
`_resolve_outfit` used to splice into `rationale_text` are **removed outright**, not kept
unused: per §33 no card ever shows a citation, and 008's only other citation surface (the
assistant-bubble text) no longer exists as a distinct rendering path once outfit replies always
go through the pager. `rationale_text` is now always the plain joined rationale text with no
embedded markers. This is a clean removal rather than dead weight retained "just in case" —
consistent with not carrying forward code with no remaining caller. Citation data is not lost
forever: `Rationale.cites` and `SuggestResult.sources` remain on the pipeline's own unmodified
`ScoredOutfit`/`SuggestResult` types (Principle I), so feature 010 (Outfit detail, which *does*
need citations per its own spec) can re-resolve them at that time — either by widening the
`outfits` schema with its own migration, or by keeping citations only ever computed from a live
pipeline result and never persisted, which is 010's decision to make, not this one's.

`StylingOutfit` gains `id: str | None` — the saved-outfit id once the user has saved that card
in the current session, `None` until then. This is the frontend's only signal for whether a
card's heart should render filled; it needs no client-side favorite cache because conversation
state (§25) is never persisted across a reload, so there is no scenario in this feature where a
previously-fetched, not-yet-saved card's saved status must be re-discovered after the fact.

Frontend must regenerate `schema.d.ts` against the running backend once this lands (handoff
trap #6).

## 36. Feature 009 (Suggestion pager) — the card's "outfit title" has no source

**Status: decided.** Not one of the handoff's four named traps, but a real gap found while
building the card: § Outfit suggestion pager item 1 specifies a header row starting with
"outfit title (13px/700, truncates)", and § Screen anatomy → Outfits/Outfit detail confirm this
is a genuine, **user-editable, persisted** field on a *saved* outfit (the gallery card's inline
rename, Outfit detail's `TopHeader` title). Nothing produces this value for a fresh, unsaved
suggestion: `ScoredOutfit`/`StylingOutfit` carry no title anywhere, and the reference prototype's
own simulation only appears to solve this because its demo data pre-seeds every outfit
(including ones a chat reply merely "shows") with a title invented at mock-data-authoring time —
not something a real pipeline reply produces (`design/prototype/What to Wear.dc.html`'s
`pagerCards` mapping reads `o.title` off already-existing `s.outfits` state; reference only, nothing
from it is ported).

**Decision**: the pager card's title is the **occasion text** (`meta_line`'s own first segment,
i.e. `Context.occasion` — no separate computation), truncated with the existing ellipsis
treatment. No new "title" concept or column is introduced in this feature's schema; `occasion` is
the only string 009 has that plausibly reads as a title, and reusing it costs nothing new to
store. The gallery's separate, editable, persisted title (010's own concern) can seed itself from
this same `occasion` value at save time and diverge from there once a user renames it — that
seeding is 010's migration to write, not this one's, since 009's `outfits` table has no `title`
column and none is added here (minimal-schema principle, §32).

**Rejected**: adding a `title` column to `outfits` now, generated as a copy of `occasion` at save
time — plausible, but speculative for a feature that never reads or displays a *separate* title
value anywhere in its own scope (the card always shows `occasion` directly, never a divergent
stored copy); 010 can add exactly this column, seeded correctly, when it actually needs one to
be independently editable. **Rejected**: leaving the header title blank/omitted — contradicts the
design system's explicit, twice-stated anatomy item.
## 37. Conversational styling turns — amends §28

**Status: decided.** Reverses §28's core decision. §28's own text stays as the record of what
was believed at the time; this is what replaces it and why.

### What §28 decided, and what was wrong with it

§28 ruled that the composer's send is **local-only** — it appends to the transcript and never
calls the backend — with "Start styling" the sole trigger for `POST /recommend/messages`. The
consequence shipped in 008 and survived 009: the chat looks conversational, but only the user
is talking. There is no assistant reply between messages.

The reasoning was not careless, and two of its three legs still hold. What failed is the same
failure this project keeps rediscovering: **the option list was incomplete.**

§28 weighed exactly two alternatives and rejected both correctly:

- *(a) every send runs the real pipeline.* Rejected for cost and latency — "a full
  retrieval+LLM call on every single message with no user control over when the expensive call
  fires."
- *(b) a backend endpoint returning a canned acknowledgement.* Rejected because the text would
  be "discarded, ephemeral, and has no reason to be server-authoritative."

The option it never considered is the one that was wanted: **a lightweight conversational turn
— no retrieval, no wardrobe, no generation — whose output is not discarded but accumulates into
the intent that "Start styling" later consumes.** Neither rejection reaches it. It has none of
(a)'s cost, because it never touches retrieval or the pipeline; and it is the opposite of (b),
because its output is precisely what makes the later expensive call better.

### The evidence §28 weighed wrongly

§28 built its case on the reference prototype's simulation code, where `sendMessage()` returns a
canned non-AI acknowledgement. But `design-system.md` § **Chat input behavior** describes two
*distinct* states — `sending` (showing a **"Thinking…"** bubble) and `styling` (showing
**"Styling your outfit…"**) — and instructs: *"Re-enable both the instant the assistant's reply
lands."* That is a per-message request/reply cycle, in the design's own words, with its own
bubble distinct from the styling one.

§28 collapsed both states onto Start styling ("the composer's own 'Thinking…' row … apply while
a Start-styling call is in flight, not on ordinary composer sends"). Two separately-named states
with two separately-named bubbles is the stronger reading, and it is the design system rather
than throwaway prototype code — which Principle VIII ranks above it explicitly.

### The decision

Every composer send calls a **new, separate conversational endpoint**. It is not the pipeline.
"Start styling" remains the sole trigger for outfit generation, unchanged.

The conversational call returns **structured output carrying both the visible reply and the
slots it extracted** — `{reply_text, occasion?, formality?, mood?, temp_c?, location?}`. This
single shape is what makes the rest work:

- the prose is the conversation, evaluated for voice;
- the slots are data, evaluated for extraction accuracy;
- neither is judged by looking at the other.

**"Start styling" composes its request from the accumulated slots in Python, not from an
LLM-written summary.** `occasion` gates retrieval (Principle III), and
`pipeline/graph.py::_parse_refinement_intent` is deterministic *by explicit design* — its
docstring records that "refinement intent gates the selection/ranking path the same way an
occasion does, so it stays deterministic too." Letting a model freely write the string that
gates retrieval cuts against that reasoning. The model extracts; Python composes. Where no slot
was extracted, the accumulated raw user text is the fallback, which is exactly 008's behaviour.

**No pipeline change is required, and none is permitted.** `GraphState` already accepts
`occasion`, `mood`, `formality`, `location` and `temp_c`; 008 populates only `occasion` and
leaves the rest unset. Extracted slots fill fields the pipeline has always taken. That keeps
`pipeline/`, `scoring/` and `retrieval/` untouched, so `docs/eval-baselines/` cannot move.

### Consequences

- **A new LLM path**, so the Quality Bar applies in full: a prompt file under `prompts/`
  (inline prompt strings are prohibited), an entry in the golden set, LangSmith tracing, and no
  live call in CI.
- **New copy the design system does not contain.** Its Recommend table has four keys, all error
  and empty states; nothing for ordinary conversation. Principle VIII forbids inventing it in
  code, so it is drafted for the design owner to finalise, tracked as an explicit open item —
  see the handoff. Shipping improvised turn copy is not permitted.
- **`thread_id` now carries more than one real call per tap.** §25's identity decision holds,
  but 008's assumption that a thread sees exactly one backend call per Start-styling tap does
  not.
- **Cost:** a turn on every send, on the small chat model with no retrieval, capped per thread
  by config. A conversational turn is a fraction of one styling request.
- **The wrap-up is visible**, as an assistant message before the outfits — so what the system
  understood is on screen and correctable before the expensive call, rather than only inferable
  from bad results.

### Checked before deciding

Principle I requires salvaging existing AI code before writing new. `../app-legacy` has **no
conversational path** — every occurrence of "conversation" there refers to a LangGraph
checkpointer thread, not a chat turn. This is genuinely new, and nothing was reinvented.

## 38. Feature 010 (Outfit detail) — citations and per-dimension scores: server-side capture at save time

**Status: decided.** This is the handoff's own §3 gap: neither citations nor per-dimension
scores exist on the `outfits` table (0009), and Outfit detail is specified to show both.

### The gap

`outfits.rationale_text` is deliberately plain (0009's own comment: "never citation markers"),
and `match_label` is deliberately the label only, never the float (Constitution VI: no parallel
numeric scale, not even at rest). Design-system.md § Outfit detail requires **both**: inline
numbered citation `Badge`s in the description plus the numbered rule list they refer to, and a
"Match breakdown" with one bar per dimension (`color_harmony`, `formality_coherence`,
`weather_fitness`, `silhouette_balance` — `SCORE_DIMENSIONS`, `schema.py`). Both exist on the
pipeline's own `ScoredOutfit` (`.rationale[].cites`, `.scores`) at generation time, but
`_resolve_outfit` (`recommend.py`) flattens both away before the client ever sees them, and
`SaveOutfitRequest` only echoes back what the client has — which no longer includes either.

### Decision: the save route re-resolves them server-side from the thread's own checkpointed result, keyed off `thread_id`

`SaveOutfitRequest` gains a required `thread_id` (the same id already threaded through
`SendMessageResponse`/`SuggestionPager`'s save call). The route calls
`get_compiled_graph(repo).get_state({"configurable": {"thread_id": thread_id}})` and reads
`last_result: SuggestResult | None` off the returned `StateSnapshot.values` — the same field
`graph.py`'s own `score_and_rank`/`explain` nodes already populate and read back for
refinement turns (`graph.py` lines ~380, ~457). The specific `ScoredOutfit` being saved is
identified by exact ordered match against `outfit.items` (`SuggestionPager.tsx` already sends
`item_ids` in the same order `StylingOutfit.items` — itself sourced unchanged from
`ScoredOutfit.items` — so this is a reliable, already-true invariant, not a new one).

**Ownership check on the checkpointer read, not just the DB row**: before trusting
`last_result`, the route confirms the snapshot's own `state["user_id"]` equals the caller's
`user_id`. The checkpointer is per-thread application state, not a DB table — it has no RLS of
its own (`memory/store.py`'s own hardening note documents that its tables deny `authenticated`
entirely at the Postgres/PostgREST layer; the app's own pooler role reaches it directly). Skipping
this check would let user A save citations/scores by guessing or reusing user B's `thread_id`, a
narrower version of the exact checkpointer-exposure bug `memory/store.py::_harden_checkpointer_tables`
already fixed once for a different access path. This is the same "ownership checked in the query,
not only by RLS" discipline the handoff names for the `outfits` table itself, applied to the one
other piece of per-user state this route touches.

**Graceful degradation, not failure, when the thread state is unavailable or the outfit isn't
found in it** (expired `InMemorySaver` state after a restart, a `thread_id` the client didn't
send, or an outfit saved so long after generation that the checkpointer already evicted it — none
named by the handoff, all real given `get_checkpointer()`'s own documented fallback to
`InMemorySaver` when no reachable Postgres is configured): the save still succeeds, with empty
citations and an empty score list. This mirrors Constitution IV's own fallback clause ("where the
deterministic fallback produces an outfit with nothing honest to cite, it MUST return an empty
citation list rather than fabricate one") — extended here from "the pipeline had nothing to cite"
to "this route can no longer prove what the pipeline cited," which deserves the identical honest-
empty treatment, not a hard failure on an otherwise-successful save.

### Schema (migration `0010`)

Two new columns hold what's needed to reproduce the exact inline-badge rendering, plus one for
the score bars — all additive, `outfits.rationale_text`/`match_label` untouched:

```sql
alter table outfits
  add column rationale_with_citations text not null default '',
  add column citations jsonb not null default '[]'::jsonb,
  add column dimension_scores jsonb not null default '[]'::jsonb;
```

- `rationale_with_citations` — the same rationale text as `rationale_text`, but with `[n]`
  markers appended after each rationale segment that cited something, numbered in first-appearance
  order across the outfit's own rationale — **exactly** the marker convention `bdc9ad4 fix(008):
  inject [n] citation markers into rationale_text` already built, used, and then removed once 009
  moved every outfit reply onto the citation-free pager (design-decisions.md §33/§35). Resurrected
  here verbatim rather than re-invented, since it was working, tested code with a proven frontend
  parser (`ChatMessageList.tsx`'s old `renderWithCitations`/`CITATION_TOKEN` regex, also
  resurrected — see the plan's data-model.md).
- `citations` — `[{number, text}]`, exactly old `CitedRule`'s shape: the numbered rule-list rows
  the markers point at (`text` = `CitedSource.source`, the human-readable reference — not a rule's
  styling guidance itself; `rule_id`/`url` aren't persisted since nothing in the design renders
  either).
- `dimension_scores` — `[{dimension, value}]`, one entry per `SCORE_DIMENSIONS` value when
  present. `DimensionScore.reason` is **not** persisted — no surface in design-system.md ever
  renders a scorer's reason text, and storing it would be schema for a field with no reader
  (Quality Bar: no abstraction without a measured problem). `value` is stored and transmitted in
  the API response (needed to compute each bar's fill width) but is never rendered as visible text
  — storing/transmitting a float is not the violation Constitution/§ Scores forbids; rendering one
  as a number is.

**Why not reuse `rationale_text` itself for the marked-up version** (considered first, since it's
the cheaper diff): `rationale_text` is already the **final, space-joined** string
(`" ".join(text_parts)` in `_resolve_outfit`) by the time it reaches the client and gets echoed
back — per-segment boundaries are gone by then, so there is no way to recover *where* a marker
should go from the plain text alone. The marked-up version has to be built fresh from
`last_result`'s own `Rationale` list (which still has per-segment `cites`) at save time, so it is
necessarily a second column, not a repurposing of the first. Keeping `rationale_text` itself
untouched also means 0009's own documented invariant ("never citation markers") stays true for
every row, old and new — nothing downstream that trusts that comment breaks.

**Rejected alternatives:**

| Option | Rejected because |
|---|---|
| **(a) chosen** — server re-resolves from the thread's checkpointed `last_result` | — |
| (b) `StylingOutfit` returns citations/scores in `SendMessageResponse`; client echoes them on save | This is the handoff's own option (b): a client can then assert which styling rules justified an outfit and what it scored — exactly what Principle IV (grounded output only) and Constitution II (LLM must not compute or override a score) exist to prevent, since nothing server-side would verify a client-supplied citation or score before it reaches storage and, later, the screen. |
| (c) Outfit detail omits both, showing only items/description/match label | The handoff's own option (c): contradicts design-system.md in two separately-specified places (§ Outfit detail, § Badge) and removes the only content that distinguishes detail from the gallery card — the entire reason a user opens it. |
| Re-run the pipeline at save time (or at detail-view time) to regenerate citations/scores fresh | Explicitly out of scope per the handoff (§5): re-running generation produces *different* reasoning than the outfit the user actually saved and is judging — the saved outfit's citations/scores must be a record of what was actually shown, not a fresh computation that happens to reuse the same items. Also a `pipeline/` call this feature has no business making (Constitution I: pipeline behaviour is out of scope). |
| Fail the save (4xx) when thread state is unavailable, instead of degrading to empty | Punishes the user for infrastructure state they have no way to know about or control (an evicted in-memory checkpoint, a stale `thread_id`) by blocking an otherwise-valid save of an outfit they already committed to keeping. The empty-citations/empty-scores degrade path costs nothing extra to implement (both are already nullable-shaped, `[]` being a valid "nothing to show" state design-system.md already expects for the "nothing to cite" case) and matches Constitution IV's own precedent for the identical shape of gap. |

## 39. Feature 010 (Outfit detail) — "Log as worn today" logs the outfit and every item in it

**Status: decided**, via `/speckit-clarify` (spec.md, session 2026-08-02) rather than assumed
during planning — this is exactly the kind of product call the handoff says belongs to a human,
not a silent default, and the initial recommendation going into clarification (outfit-level only,
no item propagation) was overridden on review.

### The gap

`item_wears` (0005) is per-item. Outfit detail's overflow sheet offers "Log as worn today" for
the *outfit* as a whole, and design-system.md's own Outfits filter/sort spec (§5, Filter & sort
dimensions) lists "Most worn" as a sort facet for **outfits**, which `item_wears` alone cannot
answer — a new outfit-scoped notion of "worn" is needed regardless of what else it does.

### Decision: both. A new `outfit_wears` table for the outfit-level sort, plus an `item_wears`
upsert for every item still owned by the caller

Logging an outfit as worn writes:
1. One `outfit_wears` row (upsert, no-op on repeat), giving "Most worn" something to sort by.
2. One `item_wears` row **per item currently in the outfit that the caller still owns** (the
   exact `record_wear`-shaped `INSERT ... ON CONFLICT (item_id, worn_date) DO NOTHING` 005 already
   uses), silently skipping any item id no longer present in the caller's wardrobe rather than
   failing the whole action — an outfit can legitimately reference an item the user later removed
   from their closet (see spec.md Edge Cases), and that item obviously cannot receive a wear
   record that no longer has an owner-verified row to attach to.

Both writes happen in the same transaction as one route/repository call — a wear log split across
two round trips risks a half-applied state (outfit marked worn, items not, or vice versa) that a
retried request could then double up on the side that succeeded. Idempotency is per-row
(`unique (outfit_id, worn_date)` / `unique (item_id, worn_date)`), so retrying the whole
transaction after a partial failure is always safe.

**Why both, not one:** the clarification's own reasoning is definitive here — physically wearing
an outfit *is* wearing every item in it, so an item-level wear ledger that never reflects
outfit-driven wears would silently under-count actual wear for any item a user only ever wears as
part of a saved outfit rather than tapping "Log as worn" individually from Item detail. The
initial recommendation (outfit-level only) was based on "nothing today reads a per-item wear
count in the UI" being true right now, but that's a fragile justification — item_wears existing
at all (0005) already anticipates a future reader, and letting outfit-driven wear silently not
count toward it would make that future reader's data wrong from day one, not just incomplete.

### Schema (migration `0010`)

```sql
create table outfit_wears (
  id uuid primary key default gen_random_uuid(),
  outfit_id uuid not null,
  user_id uuid not null,
  worn_date date not null default current_date,
  created_at timestamptz not null default now(),
  unique (outfit_id, worn_date),
  foreign key (outfit_id, user_id) references outfits (id, user_id) on delete cascade
);

alter table outfits add constraint outfits_id_user_id_key unique (id, user_id);

alter table outfit_wears enable row level security;

create policy "outfit_wears_modify_own" on outfit_wears
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

grant select, insert, update, delete on outfit_wears to authenticated;
```

Same shape as `item_wears` (0005) exactly: one row per entity per calendar day
(`unique (outfit_id, worn_date)`), a composite FK against `(outfits.id, outfits.user_id)` so a
forged `(outfit_id, user_id)` pair is rejected at the database level (proven the same way 0005's
`test_wardrobe_rls.py::TestItemWearsRLS::test_user_cannot_insert_a_wear_row_against_another_users_item`
proves it, mirrored for outfits), and RLS + GRANT per the `0002` pattern. No `item_wears` schema
change at all — the per-item writes this decision also makes go through the existing
`record_wear`-shaped statement unchanged.

**Rejected alternatives:**

| Option | Rejected because |
|---|---|
| **(a) chosen** — new `outfit_wears` table, and an `item_wears` upsert per item | — |
| (b) Outfit-level only, no `item_wears` writes | The initial recommendation before clarification; overridden because it would make item-level wear data silently wrong (undercounted) for any item worn only via outfits, not merely incomplete-until-a-future-feature as first framed. |
| (c) `item_wears` writes only, no `outfit_wears` table (derive "most worn outfit" by joining through `item_ids` at read time) | Rejected — an outfit's "worn count" would have to be some aggregate over its items' wear rows (max? min? mean?), which is a made-up combination rule with no obvious right answer, is expensive to compute at read time for a sort, and produces a nonsensical result the moment an outfit's `item_ids` no longer perfectly reflects what was worn together (an item removed from the closet after the fact, e.g.). A first-class `outfit_wears` row answers "was *this outfit* worn today" directly and unambiguously, same as `item_wears` does for a single item. |
| A `last_worn_at` timestamp / `worn_count` integer column on `outfits` instead of a table | Rejected for the identical reason 005 rejected both shapes for items (§22.1): can't answer "most worn" as a count over time, can't be an idempotent, undoable-in-principle audit trail, and a bare counter is exposed to the same accidental-double-tap inflation problem 005 already reasoned through — this feature's overflow sheet gives "Log as worn today" no confirmation or on-page feedback either, so the identical double-tap blind spot applies. |

## 40. Feature 010 (Outfit detail) — Delete requires confirmation

**Status: decided.** The handoff explicitly asks this be decided deliberately per feature rather
than copied from 005's own flagged-as-a-gap precedent.

### Decision: yes, confirm — reuse 005's exact bespoke dialog pattern

Deleting a saved outfit shows the same bespoke confirmation `<dialog>` design-decisions.md §22.2
already built for closet items (title `Delete {outfit title}?`, body `This can't be undone.`,
outline "Cancel" + danger-toned "Delete", `showModal()`/focus-trap/restore, safe-area-aware
bottom padding) — not a new component, the same one, parameterized by outfit title instead of
item name.

**Why the same call as §22.2, not a fresh one:** every reason §22.2 gave for closet items applies
identically here, with no material difference in stakes. A saved outfit is the record of a real
styling decision plus (as of §38) its saved reasoning — losing it to a mis-tap in a three-row menu
(Log as worn today / Edit title / Delete) is the same "harsh outcome for one imprecise tap" §22.2
already reasoned through, and the design system gives Outfit detail's overflow sheet no more
built-in friction than Item detail's had. Deciding differently here — e.g. no confirmation, since
"the design doesn't ask for one" — would produce an inconsistent app where one entity type is
protected and a materially similar one isn't, for no reason a user could explain.

**Rejected alternatives** (restated from §22.2, since they apply unchanged; not re-litigated):

| Option | Rejected because |
|---|---|
| **(a) chosen** — bespoke confirmation dialog, reusing §22.2's exact pattern | — |
| No confirmation, matching a literal reading of the design system's silence | Same failure mode §22.2 already named: a danger-toned row that *looks* risky but *behaves* with no friction at all is the worst combination, not a neutral default. |
| Soft delete + "Undo" toast | More schema and route surface (`deleted_at`, a restore path) than either this feature or 005 specifies; a deliberate future decision, not a side effect of filling this gap. |
| Browser-native `confirm()` | Untestable in design-system terms (no tokens, no copy/button control, inconsistent across browsers); the bespoke pattern already exists and costs nothing extra to reuse. |

## 41. Feature 010 (Outfits gallery) — filter facets dropped, sort-only; a data-shape gap the handoff didn't name

**Status: decided**, via `/speckit-clarify` (spec.md, session 2026-08-02). Not one of the
handoff's three named gaps — found while drafting the spec, and surfaced for a decision rather
than guessed silently, per the handoff's own standing instruction ("the failure mode to guard
against is an incomplete option list").

### The gap

Design-system.md §5 (Filter & sort dimensions) specifies three independent filter facets for the
Outfits gallery — Occasion (All/Dinner/Commute/Work/Everyday), Weather (All/Rainy/Mild/Warm/Cold),
Formality (All/Casual/Business casual/Formal) — plus a sort (Date added/Favorited
first/Most worn). None of the three filter facets has a reliable source in the `outfits` table as
it exists after 009: `occasion` is free pipeline-normalized text (e.g. "a rainy Tuesday commute"),
never one of the four fixed values; `meta_line` collapses formality-or-weather into a single
human-readable string chosen by which one the pipeline detected (design-decisions.md §34) — the
two can't even be told apart from the stored string alone, let alone bucketed into the design's
fixed options.

### Decision: ship sort only; filtering is a deliberately deferred gap, not built

Date added (default), Favorited first, and Most worn (§39's new `outfit_wears` count) all ship.
Occasion/Weather/Formality filtering does not ship in this feature — the "Filter & sort" pill
becomes, for now, a sort-only trigger (no facet chips, no non-"All" count badge, no "Clear" link,
since nothing is ever in a non-default filtered state to clear).

**Rejected alternatives** (presented at clarification; the deferral above was the chosen answer):

| Option | Rejected because |
|---|---|
| **(a) chosen** — drop filtering, ship sort only, record the gap | — |
| (b) Bucket into the fixed categories at save time, from the pipeline's own `Context` (new columns, populated when an outfit is saved) | The technically complete fix, and the one this section would have implemented absent the clarification answer — `Context.formality` (six-value enum) collapses cleanly to the three formality buckets, and `Context.occasion`/`condition` could be keyword-classified into the four occasion/four weather buckets. Not chosen now because the product owner explicitly deprioritized it ("keep it somewhere so we don't miss it, but it's not important for now") rather than declining it outright — this remains the recommended shape for whichever future feature picks it back up, to avoid re-deriving it from scratch. |
| (c) Match against the stored free text at read time (keyword/substring matching against `occasion`/`meta_line`) | Rejected on its merits regardless of the clarification answer — free text like "a rainy commute" won't reliably match a fixed filter option, and formality has no textual representation to match against at all once `meta_line` chose weather over it for that reply. Fragile in a way that would look like a bug ("I filtered to Formal and my formal outfit didn't show up") rather than a clearly-scoped absence. |
| (d) Keep only the Occasion filter, drop Weather/Formality | Considered as a middle ground before the clarification question was asked — still doesn't solve the underlying problem (free text still doesn't cleanly match a 4-value fixed list) and produces a half-working filter UI that's arguably more confusing than no filter UI at all. Superseded by the clarification answer, which dropped all three uniformly rather than picking a "least broken" one to keep. |

**Not lost**: this section itself is the record `known-gaps.md`-style features use elsewhere in
this project — a future feature can implement option (b) directly from this write-up without
re-deriving the bucketing approach from scratch.

## 42. Every generated outfit is now saved automatically — amends §32 and §38

**Status: decided.** A direct product request during feature 010's own testing pass, not a gap
found while building — but it reverses the persistence model §32 and §38 recorded, so it's
documented with the same rigor: what changed, what it obsoletes, and what was rejected.

### The request

"I want them all to be saved" — every outfit a styling reply surfaces should be persisted the
moment it's generated, with no heart tap required. Clarified explicitly (not assumed): this
means true zero-interaction auto-save, favorited by default, not a "Save all" button the user
still has to press.

### The decision

`POST /recommend/messages` now persists every outfit it returns, in the same request, before
the response is sent. Concretely:

- For each `ScoredOutfit` that clears the "not surfaced" floor (§ Scores, unchanged), the route
  builds the view (`_resolve_outfit`, now returning a lightweight `_ResolvedOutfit` — rationale
  text, resolved items, label — rather than the final response model directly) and, in the same
  loop, calls `SupabaseOutfitRepository.create(...)` for it, using the pipeline's own in-hand
  `ScoredOutfit`/`SuggestResult.sources` to build `rationale_with_citations`/`citations`/
  `dimension_scores` (the same `_build_rationale_with_citations` helper §38 introduced —
  unchanged in what it computes, only in when and how it's invoked).
- `StylingOutfit.id` changes from `str | None = None` to a required `str` — every outfit this
  route ever returns already has a row. `StylingOutfit` also gains a required `favorite: bool`
  (always `true` at creation — the row's own default) so the frontend can render the heart's
  fill state from the response instead of assuming.
- `POST /recommend/outfits` (the manual save route `SaveOutfitRequest`/`save_outfit` implemented)
  is deleted outright, along with `_get_state_for_thread` — both are dead code the moment nothing
  calls them, per this project's own "clean removal, not retained dead weight" convention (§35
  did the same for the `[n]`-marker embedding once its only caller went away). The heart
  (`SuggestionPager.tsx`) now only ever calls `POST /recommend/outfits/{id}/favorite` — never a
  create — because every card already has a real `id` from the moment it renders.

### This obsoletes §38's checkpointer-lookup mechanism entirely, not just its call site

§38 solved "how does a *later* save action recover citations/scores" by reading the pipeline's
checkpointed `GraphState` back out for a given `thread_id` — a real but inherently fragile
mechanism (the state might have evicted, the thread might not match, ownership had to be
re-checked against a second piece of per-user state with no RLS of its own). Auto-save at
generation time deletes the entire problem it solved: citations/scores are captured from data
already sitting in a local variable in the same function, in the same request, with no
checkpointer read, no thread-ownership check, and — critically — **no degrade path**, because
there is no longer a window in which the data could be unavailable. This is a strictly simpler
and more robust mechanism than §38's, not a smaller version of it. §38's own text is left
standing as the record of what was true before this section, per this document's convention of
amending forward rather than editing history (matching how §37 relates to §28).

### A correctness fix folded in here: persisted `item_ids` must match what was shown, not the pipeline's raw list

While implementing this, a real discrepancy surfaced: a `ScoredOutfit.items` list may legitimately
include a shared-catalog item id (Constitution IV allows citing the catalog, not just the user's
own wardrobe), but `_resolve_outfit`'s `wardrobe_by_id` lookup — used to build the *displayed*
`items` — only ever contains the caller's own wardrobe, so a catalog item silently never appears
in what's shown. The old manual-save flow never hit this because the client could only ever echo
back `item_ids` it had actually received (already catalog-filtered by construction). Auto-save,
persisting server-side, had no such filter for free — the first version of this change passed
`scored_outfit.items` (the pipeline's raw list) straight to `create(...)`, which would have stored
a catalog item's id in a row whose displayed items never included it. Fixed to persist
`[item.id for item in resolved.items]` instead — the same filtered list already used for the
response — so the stored row and what was shown always agree. Covered by
`test_outfit_including_a_catalog_item_persists_only_the_owned_ones`.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — auto-save every outfit at generation time, no tap | — |
| (b) "Save all" button next to the pager — one deliberate tap saves the whole batch | The recommendation offered before asking; explicitly declined once the user clarified they wanted zero interaction, not a lower-friction bulk action. Would have been the smaller, more reversible change (closer to §32's original model), but isn't what was actually wanted. |
| Keep the manual save endpoint alongside auto-save, for API completeness / a hypothetical future caller | Rejected on the same grounds §35 already established for this exact shape of question: no code is kept "just in case" once its only caller is gone — a second, unused way to create the identical row is a liability (two paths to keep in sync, e.g. this feature's own item_ids-filtering fix would have had to be applied to both) with no present benefit. |
| Keep `_get_state_for_thread`/the checkpointer-lookup path for `send_message` too, rather than reading `result` directly | There is nothing to look up — `result` (the `SuggestResult` just produced by this very request) is already the freshest, most authoritative copy of the data the checkpointer would have been asked to reproduce. Reaching into the checkpointer here would be strictly worse: an unnecessary round trip to fetch a copy of data already in scope. |

### Consequence for §36 (the card's title)

Unchanged in substance — `title` is still seeded from `occasion` at the moment of creation, still
user-editable after. What changes is only *when* that creation happens (now always, at generation
time, rather than only if/when a user saved it).

## 43. "Favorite" defaults to false now that "saved" is unconditional — amends §42

**Status: decided.** Caught immediately on review of §42: the first version of auto-save also
defaulted every new row's `favorite` to `true`, inherited unchanged from the pre-§42 model where
a row's mere existence *was* the save action (§32's own words: "the row's mere existence *is*
'saved'"). Once §42 makes existence unconditional, that inherited default silently claims every
single recommendation is already liked, sight unseen — which was never asked for and isn't true.

### The decision

`favorite` and "is this outfit saved" are now fully independent: every outfit is saved
unconditionally (§42), and `favorite` starts `false` — a genuine, user-set preference the heart
tap expresses, not a side effect of generation. Concretely:

- `outfits.favorite`'s column default changes from `true` to `false` (`0010`'s own migration,
  amended in place rather than via a new `0011` — see the file's own note on why: this schema is
  still local to this unmerged feature branch, not yet a precedent anyone has built on).
- `send_message`'s `StylingOutfit` construction changes from the literal `favorite=True` to
  `favorite=False`, matching the row's own new default rather than re-asserting a stale one that
  could silently drift from it.
- Existing rows are left untouched by the migration — each already reflects a real, explicit
  favorite/unfavorite action taken under the pre-§42/§43 model (a heart tap actually happened to
  produce that `true`), so there is nothing dishonest about leaving history alone.

### Why this isn't a step backward from "I want them all saved"

The request was specifically that saving require no interaction — it was not a request that every
recommendation also be marked as liked. Conflating the two would make "favorite" (and the
"Favorited first" sort it drives) meaningless: if every row is `true` from birth, favoriting stops
being a signal of anything, and the gallery's own sort-by-favorite option degenerates into
sort-by-nothing until a user starts *un*favoriting things to make room for a real signal — the
opposite of how a preference marker should work. Starting `false` and letting the user opt specific
outfits *up* is the only shape where "favorite" still means something once "saved" no longer does.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — `favorite` defaults to `false`; independent of the now-unconditional save | — |
| Keep `favorite` defaulting to `true` (the version this section replaces) | Directly contradicted by the correction that prompted this section — conflates "the app decided to keep this" with "the user likes this," which are no longer the same event once every recommendation is saved regardless of merit. |

## 44. Feature 011 (Chat history) — what a "session" is, and what writes one

**Status: decided.** This is the handoff's own §3.1 gap: no `sessions` table exists, `thread_id`
is minted by the pipeline (§25) but nothing durable survives a page reload, and "New chat"
currently only resets local state because — per §28, echoed in the 011 handoff — "there was
nothing to archive into."

### The gap

Design-system.md says New chat "archives the current thread as a Chat history session." The
handoff frames the central question as *when* that archive happens: on "New chat" (archive-on-
demand) or continuously from the first message (written-on-start), and names the crash-safety
difference between them. But the handoff's own §7 definition of done is the sharper signal, not
just the framing: *"I have a conversation, reload the page, and find it in Chat history"* — with
no archive step mentioned at all. A model where nothing is durable until "New chat" is tapped
cannot satisfy that line: a user who sends one message, gets a reply, and reloads without ever
touching "New chat" would find nothing.

### Decision: written-on-start, keyed on `thread_id` itself, upserted by the existing route

A `sessions` row is created the moment a thread receives its **first** user message — inside
`POST /recommend/messages`, in the same transaction that already persists the turn's outfits
(§42). Every subsequent call for that `thread_id` updates the same row (bumps `updated_at`) and
appends new `messages` rows; nothing is ever created a second time for one thread.

The session's identity **is** `thread_id` — `sessions.id` is not a second, independently
generated uuid, it is the pipeline's own thread id, stored as the primary key. `/history/
:sessionId` therefore takes the same value `POST /recommend/messages` already accepts as
`thread_id`, with zero translation between "session id" and "thread id" anywhere in the system.
Rejected: a separate `sessions.id` with a `thread_id` foreign column pointing at it — two ids for
one concept, with no caller anywhere that ever needs them to differ; every join, lookup, and
route parameter would carry the extra indirection for no benefit. `thread_id` is already the
correct primary key by definition (§25: the pipeline mints exactly one per logical conversation).

**Consequence for "New chat": there is nothing left for it to do on the backend.** Once a session
is written from the first message, "archiving" is not a discrete action — every thread with a
user turn is, continuously, already a Chat-history session from that point on. `newChat()` stays
exactly what it is today (`RecommendChat.tsx`'s local `setMessages([]); setPendingTexts([]);
setThreadId(null)` reset, per design-decisions.md §25) — no new endpoint, no archive call. The
existing guard — disabled whenever the thread has no user turns — is kept unchanged; it no longer
prevents "archiving a blank session" (written-on-start means a session with zero user turns was
never created in the first place, so there is nothing to blank-archive), but it still prevents a
confusing no-op reset on a thread that already reads as empty, and changing it was never asked
for.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — written-on-start, upserted inside `POST /recommend/messages`, keyed by `thread_id` | — |
| (b) Archive-on-demand — a new endpoint "New chat" calls, sending the accumulated client-side transcript to be written in one shot | Fails the handoff's own DoD line: a reload before "New chat" is ever tapped loses everything, which is precisely the crash-safety gap the handoff itself calls out as (b)'s weakness. It also re-sends data the server already produced and could have kept — the client would be round-tripping a transcript the backend generated in the first place, just to get it archived. |
| (c) Treat the pipeline's own LangGraph checkpointer as the source of truth for history — read its serialized state back per-thread instead of a dedicated `sessions`/`messages` table | The checkpointer's state is opaque, LangGraph-internal serialization, not a shape a "list every session, ordered, with a preview and count" query can be run against. §38 tried exactly this pattern for a narrower problem (recovering one outfit's citations from checkpointed state) and §42 replaced it, in the same document, for being "a real but inherently fragile mechanism" — evictable, thread-matching-dependent, no ownership of its own. Reusing it here would resurrect the exact fragility §42 just removed, for a harder version of the same problem (a full list screen, not one lookup). |

## 45. Feature 011 (Chat history) — outfits linking back to their conversation

**Status: decided.** The handoff's own §3.2 gap: `outfits` has no `thread_id` or session
reference, but both Chat history's row and Session detail need an outfit count, and `POST
/recommend/messages` already has `thread_id` in scope at the exact moment it auto-saves each
outfit (§42).

### Decision: a nullable `outfits.thread_id`, populated only going forward; count is `COUNT(*)`, never stored

`outfits` gains one nullable column, `thread_id uuid references sessions(id) on delete set
null`. `send_message` sets it on every `outfit_repository.create(...)` call from this feature
onward — the value is already a local variable in that function (§42's own reasoning for why
this is cheap: "already sitting in a local variable in the same function, in the same request").
Existing rows are left untouched: `thread_id` stays `null` on every outfit created before this
migration, because nothing durable ever recorded which thread produced it, and any attempt to
infer one (matching by `occasion` text, by timestamp proximity, or any other heuristic) would be
exactly the "silently defaulted" failure mode the handoff's own trap list names — a guessed link
is worse than an honest absence of one, because it can be *wrong* in a way "no link" cannot.

The outfit count a session shows — both the Chat-history row's third line and Session detail's
"View in Outfits" button — is computed live: `SELECT COUNT(*) FROM outfits WHERE thread_id =
:session_id`. It is never a denormalized counter column on `sessions`. A pre-existing outfit
(`thread_id IS NULL`) can never satisfy `= :session_id` for any real session id, so it correctly,
automatically counts toward none of them — no special-cased "is this outfit too old to link"
branch is needed anywhere in the query or the route; the honest answer falls out of `IS NULL`
never equalling a uuid. Pre-existing outfits remain fully visible in the (unaffected) Outfits
gallery; they simply never appear to have come from any particular conversation, which is the
truth.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — nullable `outfits.thread_id`, set only for outfits created after this migration; count is a live `COUNT(*)`, pre-existing rows naturally excluded via `IS NULL` | — |
| (b) Backfill pre-existing rows with a best-guess `thread_id`, inferred from `occasion`/`created_at` proximity to some other record | No durable field on any pre-011 row ties it to a specific pipeline thread — the checkpointer state that ran that request is not reliably still present, and even if it were, matching it up after the fact is a guess dressed as data. This is the exact shape of defect the handoff's §8 warns has "shipped four times" on this project: a value silently defaulted or inferred rather than honestly absent. |
| (c) A denormalized `outfit_count` column on `sessions`, incremented at outfit-create time | Same objection design-decisions.md §41 already settled for outfit-gallery's own "most worn" sort: a counter can drift from reality (a failed or partial write leaves it wrong with no way to detect the drift), where a live `COUNT(*)` against the real rows cannot ever be wrong by construction. At this feature's scale (personal-app row counts), the query cost of counting live is not a real tradeoff against that correctness guarantee. |

## 46. Feature 011 (Chat history) — what "citation Badges" in the archived view actually renders

**Status: decided.** Not one of the handoff's two named decisions, but a real gap found while
reading the handoff closely against already-settled design-decisions — the same shape of gap
§33 and §36 each found in earlier features, so recorded with the same rigor.

### The gap

Handoff §4.3 asks for Session detail to show "the same user/assistant bubble treatment as
Recommend, including citation Badges." But §33 and §35 (both already decided, before this
feature) establish that **no live chat surface shows citation Badges at all, anywhere, as of
today**: § Badge and § Outfit suggestion pager both say the tone is "used only in Outfit detail's
description, never in the chat outfit card," and §35 went further — removing the older
bubble-plus-inline-`[n]`-badges rendering path outright once every outfit-bearing reply started
going through the (citation-free) pager, "no remaining surface, at any outfit count." Taken
literally, the handoff is asking this feature to archive a rendering treatment that does not
exist in the thing it's supposedly a read-only copy of.

### Resolution

"Same bubble treatment as Recommend" is read as the visual chassis (the rounded user/assistant
bubble shapes and alignment `ChatMessageList` already renders), not as "reproduce today's live
content-rendering path" — because that path, for an outfit-bearing reply, is the pager, and the
handoff explicitly forbids reproducing the pager's own thumbnails/rule-list in the archived view
one clause later. The citation Badges the handoff asks for are sourced from data that already
exists precisely because of this: each outfit's own `rationale_with_citations`/`citations`
(captured server-side at save time, §38, unaffected by §42/§43). A `styling_reply` message row
(§ data-model.md) carries the ids of the outfits that turn produced; Session detail resolves each
one and renders **its** `rationale_with_citations` — through the same `renderWithCitations`
token-splitting helper `RationaleWithCitations.tsx` already uses for Outfit detail — as the
assistant's bubble content for that turn, with the item-thumbnail grid and the numbered rule-list
rows Outfit detail also shows for that same text deliberately omitted (the handoff's own stated
asymmetry, §4.3, kept intact). A reply that produced no outfits shows its plain `reply_text`
(the honest empty-citation copy the rest of the product already uses) with no citation Badge at
all, matching Constitution IV's "empty citation list rather than fabricate one."

This introduces no new citation surface and no new data: it is Outfit detail's own already-
grounded text, rendered a second time in a different chrome, for a screen the design system
explicitly asks to show it.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — archived `styling_reply` bubbles render each linked outfit's own `rationale_with_citations`, citation-badged, without thumbnails/rule list | — |
| (b) Take the handoff's wording literally and resurrect the pre-§35 bubble-plus-inline-badge rendering path, live-only, just for this screen | Reintroduces a rendering treatment §35 deliberately and explicitly removed as having "no remaining surface, at any outfit count" — resurrecting it for one screen contradicts that decision rather than building on it, and there is no data left to feed it: `SendMessageResponse.citations` and the `[n]`-marker splice were removed outright, not deprecated. |
| (c) Render outfit-bearing turns with no citations at all, treating the handoff's line as stale/superseded and dropping it | Closest to "do nothing," but the data to satisfy it honestly already exists (§38's per-outfit citation columns) and costs nothing new to surface — dropping a design requirement outright when a grounded, no-new-surface way to satisfy it is available isn't the smaller change, just a less complete one. |
| Add a third state (e.g. `null`/"undecided") distinct from both `true` and `false` | Would need a schema change (nullable boolean or a new enum) for a distinction the product doesn't currently use anywhere — no screen renders an "undecided" heart state, only filled/outline (§ Outfit suggestion pager, § Outfits gallery). Boolean `false` already *is* "undecided, leaning not-yet-expressed" for every practical purpose this app has today; a third state would be speculative. |

## 47. Feature 016 (Conversational turns) — where accumulated slots live

**Status: decided.** The handoff's own §4.2/§8 open question. §37 names the checkpointer as
"the obvious candidate" and asks for the choice to be recorded with alternatives — this is that
record.

### Decision: the pipeline's own LangGraph checkpointer, read/written directly via `CompiledStateGraph.get_state`/`update_state`, never via `.invoke`

`pipeline.graph.get_compiled_graph(repo)` already compiles with `checkpointer=memory.get_checkpointer()`
(`graph.py::compile_graph`) — the same Postgres-or-in-memory-backed store `original_context` and
`refinement_deltas` already rely on for durability across turns on one `thread_id` (`GraphState`'s own
docstring: "persisted across invokes on the same thread_id by the checkpointer"). `CompiledStateGraph`
exposes `get_state(config)`/`update_state(config, values)` as first-class LangGraph API for reading and
patching a thread's checkpointed state **without running any node** — no `START` edge fires, no
`gather_context`/`wardrobe_retrieval`/`generate_outfits` node executes. That is what makes this
satisfy the handoff's "no retrieval, no wardrobe load, no pipeline invocation" constraint literally:
"invocation" means running the graph, not touching its checkpoint.

The conversational-turn call therefore does exactly this each turn:

1. `values = graph.get_state(config).values` — read whatever slots a prior turn already wrote (`{}` on
   a thread with no checkpoint yet, not an error).
2. Extract new slots from the user's message via the LLM (§ new `conversation.py` module).
3. `graph.update_state(config, {k: v for k, v in extracted.items() if v is not None})` — write only the
   keys this turn actually produced a value for.

Slot keys are `GraphState`'s own field names (`occasion`, `mood`, `formality`, `location`, `temp_c`) —
per the handoff's explicit instruction ("slot names match `GraphState`'s existing fields exactly") —
written into the exact same state object those fields already occupy for a real pipeline run. Because
`GraphState` has no custom reducer on any of these keys, LangGraph's default per-key overwrite
semantics on `update_state` **already implement the accumulation rule for free**: a later turn's
`update_state({"formality": "casual"})` overwrites only `formality`, leaving `occasion`/`mood`/whatever
else untouched — this is the same last-write-wins behavior `parse_request`/`gather_context` already
depend on for refinement turns, not a new persistence idiom invented for this slice.

**"Start styling" still composes its request explicitly**, not by relying on this merge to flow through
automatically: `send_message` reads `graph.get_state(config).values` itself and builds the full
`graph.invoke(...)` input dict by hand (occasion/mood/formality/location/temp_c pulled out one by one),
even though — because both read from and write to the same checkpoint — omitting fields from the
`invoke()` call would technically let them merge in anyway. The explicit build exists because the
handoff's own definition of done requires proving "what gets passed to the graph on the Start-styling
call... by inspecting the invoke input" — an implicit merge is not inspectable at the call site; an
explicit dict is.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — checkpointer, via `get_state`/`update_state`, never `.invoke` | — |
| (b) A new `sessions.slots jsonb` column, upserted by the conversational-turn route | Requires a migration the handoff's own header flags as unexpected ("Migration number: none expected"), for a durability guarantee the checkpointer already provides for the identical `thread_id` key with zero schema change. The only argument for it — slots living next to `sessions` where they're easy to inspect in the DB — is outweighed by adding a second per-thread persistence mechanism alongside the one the pipeline already has, for the same data shape, when nothing about a JSONB column does something the checkpointer can't. |
| (c) `memory/store.py`'s existing `InMemoryStore` (`remember_interaction`/`recent_interactions`) | Explicitly in-process, non-durable — dies on a server restart or (on Railway, multi-instance) on landing on a different instance than the one that handled a prior turn. Feature 011's own "reload the page, find it in Chat history" guarantee already proves messages must survive a reload; losing every accumulated slot on that same reload while the messages that produced them are still visible would silently degrade the very outcome §37 exists to fix (a formality mentioned in turn 2 would vanish and "Start styling" would fall back to raw text) — precisely the "value accepted with a 2xx and then silently dropped" failure the handoff's §8 names as having shipped four times already. |
| (d) Reconstruct slots on demand from the persisted `messages` transcript (re-run extraction, or store each turn's raw delta and replay) | Either re-runs a non-deterministic LLM extraction a second time (the exact turn's original extraction is not guaranteed reproducible) or requires storing per-message deltas somewhere anyway — at which point that storage location is the real answer and this option has just relocated the question, with replay complexity added on top for no benefit. |

## 48. Feature 016 (Conversational turns) — the turn cap value and what counts as a "turn"

**Status: decided.** The handoff's own §4.4/§8 open question: "what the turn cap should be."

### Decision: `wtw_conversation_turn_cap: int = 6`, in `Settings` beside `wtw_wardrobe_min_items`; counts `user_message` rows per thread, lifetime (not reset by a "Start styling" tap)

A "turn" is one user-authored message accepted by the new conversational endpoint — counted by
querying existing `kind = 'user_message'` rows for the thread (`SupabaseSessionRepository`'s own
append-only table, already the single source of truth for what a user has sent; no second counter to
drift). On the call where that count would exceed 6, the endpoint skips the LLM call entirely and
returns the fixed "turn cap reached" copy (§8's draft table) instead of a generated reply — every call
after that does the same, so cost is bounded linearly in the worst case a user keeps typing past the
cap, not just at the boundary.

6 is chosen as enough room for the realistic slot set (occasion, formality, weather/temp, mood — four
questions) plus at least one correction or follow-up, while still being a small, single-digit number a
user notices as "the assistant is steering me along," matching FR-009's intent. It is a config default,
not a researched number — `wtw_wardrobe_min_items`/`wtw_wardrobe_sparse_threshold` (design-decisions.md
§11) were likewise picked as reasonable small integers rather than derived from measurement, and this
follows the same precedent.

The cap is **lifetime per thread**, not reset when "Start styling" is tapped: counting resets only in
the sense that a *brand new* thread (`thread_id = None`) starts its own count at zero.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — 6, lifetime per thread, counted from `messages` | — |
| (b) Reset the count every time "Start styling" is tapped, so each "round" of conversation gets its own 6 turns | Adds a second notion of "round" boundary nothing else in this slice needs (a thread's `messages` rows have no round marker), and undermines the cap's own purpose — a thread could accumulate unbounded LLM calls in total by tapping Start styling repeatedly, just never more than 6 between taps. FR-009 caps a conversation, not a round. |
| (c) A fixed constant in code, not a `Settings` field | Directly contradicts the handoff's explicit instruction ("Config, not a constant"). |
| (d) Count LLM calls actually made (excluding cap-reached short-circuits) rather than `user_message` rows | Same number in practice until the cap is first reached, but requires a new counter instead of reusing `messages`, for no behavioral difference — once capped, no further LLM calls happen either way, so nothing this option tracks is checkable at the persistence layer that the message count doesn't already show. |

## 49. Feature 016 (Conversational turns) — accumulated slots after a "Start styling" tap: handed off to the pipeline's own existing refinement mechanism, not reused for a second round of composition

**Status: decided.** The handoff's own §8 named-open question: "does the next turn start fresh, or
keep refining?"

### The situation

A thread can receive more composer sends *after* "Start styling" has already produced outfits once —
the composer stays visible, and 008/009 already support a second "Start styling" tap on the same
`thread_id` as a **refinement** turn: `parse_request` detects `original_context is not None` (set once,
on the first real invoke) and keyword-parses whatever `occasion` text arrives on that later invoke into
`refinement_deltas` via `_parse_refinement_intent` — unmodified, existing, evaluated pipeline behavior
this slice is constitutionally forbidden from touching (Principle I, handoff §6 trap #1).

Under 016, every one of those later composer sends *also* hits the new conversational endpoint first
(§37's core decision: "every composer send calls a new, separate conversational endpoint"), which by
default would keep extracting/accumulating slots the same way it does before the first tap. The
question is what "Start styling" should do with those slots on a *second* tap: recompose a full request
from them again (as if from scratch), or something else.

### Decision: slot composition applies only to a thread's first real pipeline invoke; every later invoke on that thread uses the pre-016 raw-text refinement path, unchanged

`send_message` checks the same signal `parse_request` itself uses — `graph.get_state(config).values.get("original_context") is None` — *before* building the invoke input:

- **`original_context is None` (first invoke on this thread)**: compose from accumulated slots, per §47
  — this is the new behavior.
- **`original_context is not None` (a later, refinement invoke)**: build the invoke input exactly as
  008 always has — `{"occasion": body.message, "thread_id": ..., "user_id": ..., "approach": "grounded"}`,
  where `body.message` is the frontend's own accumulated raw text since the last tap (unchanged
  `pendingTexts.join(" ")`, §28's mechanism, still alive for this one purpose). No slot dict is
  consulted on this path at all.

Conversational turns that happen *after* the first tap still get real, in-voice replies from the new
endpoint (the mission's promise — "every composer send" — doesn't stop applying once outfits exist),
and they still write whatever they extract into the checkpoint via `update_state` exactly as before.
That write is simply never read again by `send_message`, because every later invoke on that thread has
already committed to the raw-text refinement path. The slots are not deleted or reset — there is
nothing to reset — they are just no longer the input this particular request composes from.

**Why not keep composing from slots on every tap**: `_parse_refinement_intent` is deterministic,
keyword-driven, and reads the literal `occasion` string handed to a *refinement* invoke, looking for
phrases like "warmer" or "less formal" (`graph.py`'s own `_WARMER_KEYWORDS`/`_LESS_FORMAL_KEYWORDS`).
If `send_message` instead re-passed the *original* composed occasion (unchanged since slots don't
re-derive a new "what changed" summary), that string would almost never contain a refinement keyword,
silently starving the pipeline's own refinement path of the signal it's designed to consume — a second,
competing "what should change" mechanism would exist alongside the first, and only one of them would
actually reach `_parse_refinement_intent`. Handing off to the existing mechanism unmodified is the
Principle-I-compliant choice: reuse the evaluated refinement path exactly as built, rather than
inventing a second one that would need its own evaluation to trust.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — slots compose only the first invoke; every later invoke uses the unmodified raw-text refinement path, selected via the same `original_context` signal `parse_request` already uses | — |
| (b) Recompose the full request from accumulated slots on every "Start styling" tap, first or later | Silently defeats `_parse_refinement_intent` as reasoned above — a "warmer" follow-up would very likely produce an *identical* invoke input to the previous tap, since nothing in a slot dict encodes "compared to what changed." Outfits would appear not to respond to a refinement request, which is a worse, harder-to-diagnose failure than "slots are only used once." |
| (c) Explicitly clear/reset the checkpointed slot keys once the first invoke completes | Unnecessary extra write (an `update_state` call whose only purpose is deletion) for a value that's already correctly ignored by the read-path decision in (a) — nothing ever reads stale slots after the first invoke, so clearing them defends against a bug that can't occur given how `send_message` already branches. Simplicity over abstraction (Quality Bar) favors not adding the write. |
| (d) Track a separate "has this thread ever been styled" boolean instead of reusing `original_context is None` | Would duplicate a signal `parse_request` already computes from the exact same checkpointed state, for the exact same thread, one node earlier in the same request — a second flag that could only ever drift from the first, never add information (the same reasoning §44 gave for not storing `role` as its own column). |

## 50. Feature 016 (Conversational turns) — `POST /recommend/messages` stops inserting its own `user_message` row

**Status: decided.** Not one of the handoff's named open questions, but a real defect the mission
creates without naming: §37's "every composer send calls a new, separate conversational endpoint" means
every user-authored turn is now recorded once, immediately, by that endpoint — before "Start styling"
is ever tappable (`StartStylingButton`'s existing `visible={hasUserMessage}` guard). `send_message`
(`recommend.py`) has, since 008, *also* unconditionally inserted `body.message` as a fresh
`kind='user_message'` row on every call. Left unchanged, a first "Start styling" tap under 016 would
write the user's own words into `messages` twice — once already, per individual send, via the new
endpoint; once more, joined, via this pre-existing line — a duplicated transcript entry Session detail
(011) would render as the user having said everything twice.

### Decision: the new conversational endpoint owns every `user_message` insert; `send_message` drops its own

Because *every* composer send now reaches the new conversational endpoint first — before or after a
first "Start styling" tap, per §49 above — there is no longer a code path, reachable from the real UI,
where `send_message` is called with text that endpoint hasn't already recorded. The insert is removed
outright, not made conditional on "does a row already exist" — a conditional would only be needed if
some caller could still reach `send_message` with genuinely new, never-recorded text, and under the
architecture this slice ships, none can.

This does change tested behavior from 008/009: their existing integration tests call
`POST /recommend/messages` directly, without a prior conversational-endpoint call, and (where they
assert on it) expect a `user_message` row to exist afterward. Those tests are updated in this slice to
either call the conversational endpoint first (matching the real flow) or to assert the now-correct
absence of a route-level insert — not deleted, so the handoff's "test count has not dropped" bar still
holds, and the coverage they provided (that a user's turn is durably recorded before a styling reply)
still exists, just attributed to the endpoint that now actually does the recording.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — remove the insert from `send_message`; the conversational endpoint is the only writer of `user_message` rows | — |
| (b) Keep both inserts, deduplicate in the read path (e.g. `Session detail` collapses consecutive identical `user_message` texts) | Papers over a real double-write with a display-layer heuristic — the underlying duplicate row still exists, still counts toward `message_count` (§44), and "collapse consecutive identical text" is itself a guess that could wrongly hide a user who genuinely repeated themselves. Fixing the write is strictly simpler than adding a lossy read-time filter to compensate for it. |
| (c) Make the insert conditional on `count_user_messages(thread_id) == 0` (only insert if this is the very first message this thread has ever seen) | Silently reintroduces the duplicate for every *refinement* tap after the first, since those threads already have prior `user_message` rows from earlier conversational turns — the condition only guards the fresh-thread case, not the (more common, post-016) continuing-thread case, so it fixes the bug only partway while looking like a complete fix. |

## 51. Feature 016 (Conversational turns) — which lines are written by the model, and which are copy

**Status: decided.** Recorded after the fact, during review: the split below was implemented and
is defensible, but it was never written down, and it diverges from what the design owner chose
when asked. Four smaller choices in this same feature got sections; this one is larger than any
of them.

### What was asked, and what was built

The 016 handoff (§3) named **eight** situations needing copy and stated that the design owner
would write all eight, because `design-system.md`'s Recommend table has four keys — all error and
empty states — and Principle VIII forbids inventing UI copy in code. When the question was put
directly, three options were offered: the design owner writes them, they are drafted for the
design owner to edit, or the model improvises every line. The third was explicitly labelled the
least compatible with Principle VIII. **The design owner chose to write them.**

What shipped splits the eight:

| Situation | Source |
|---|---|
| Turn cap reached | `copy.py` — fixed string |
| Conversational call failed | `copy.py` — fixed string |
| Wrap-up on "Start styling" | `copy.py` — Python template |
| Acknowledge, nothing to ask | **Model, per turn** |
| Ask the occasion | **Model, per turn** |
| Ask formality | **Model, per turn** |
| Ask about weather | **Model, per turn** |
| Enough gathered | **Model, per turn** |

The five model-written situations have no fixed copy anywhere. The handoff's drafts for them
were moved into `prompts/conversational_turn_system.md` as **voice-calibration examples**,
explicitly marked "NOT final, approved copy and must never be reproduced verbatim; they exist
only to show the register/length/tone to match."

### Decision: keep the split, and treat the prompt as the copy artifact for those five

The split is correct even though it was not what was asked for, and the reason is specific
rather than general: **the five model-written situations are all responses to something the user
just said.** "Acknowledge what was said" cannot be a fixed string without becoming the canned
acknowledgement §28 already rejected as "demo flavor" — the thing this feature exists to
replace. A fixed "Got it." fired after every message is precisely the half-conversation §37
amended §28 to remove.

The three Python-owned lines are the complement, and the boundary is principled rather than
convenient: each fires in a moment where **there is no model reply to show at all** — the turn
cap stopped the call, the call failed, or the wrap-up is deliberately not a second LLM call
(§49). Copy exists exactly where the model is silent.

**Consequence: `prompts/conversational_turn_system.md` is a copy artifact, not just a technical
prompt.** Its voice section is where "what the assistant sounds like" is actually specified, and
it is subject to Principle VIII the same way a copy table is — changing it changes user-visible
language. It should be reviewed by the design owner when the words matter, not only by whoever
is editing extraction behaviour.

### What this does not license

This is not a precedent for generating UI copy in general. It applies to **conversational turns
whose content is a response to unpredictable user input**, and nowhere else. Every other string
in this product — every empty state, every error, every button label, including the three in
`copy.py` — remains fixed copy owned by the design system. A model writing a button label would
still be a Principle VIII violation.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — five model-written, three fixed, prompt treated as a copy artifact | — |
| (b) Fixed copy for all eight, as the handoff originally asked | Makes the acknowledge/ask lines canned, which is the behaviour §37 exists to remove. A stylist that answers every message with one of five stock sentences is the prototype's simulation with an LLM bill attached. |
| (c) Model writes all eight, including the turn cap, failure and wrap-up lines | Two of those three fire when the model is unavailable or has just failed, so there is nothing to generate them with; the wrap-up would become a second LLM call, which §49 rejected on its own merits. |
| (d) Keep the split but leave it unrecorded, as shipped | What this section fixes. The five drafts sit in a prompt file marked "not final" with no record of who decided they would never become final — a reader would reasonably conclude the copy was still outstanding. |

## 52. Feature 014 (Offline, caching and the update prompt) — cache strategy per route class, and the sign-out purge

**Status: decided.** The handoff named this the slice's central open question and explicitly
rejected "everything `NetworkFirst`" as an answer without justification (§3.1). Full reasoning in
`specs/014-offline-and-updates/research.md` R1–R6; this section is the durable record.

### What the app actually is, first

Every authenticated screen (`app/(app)/**/page.tsx`) is a plain server component with no data
fetching — all real data comes from `"use client"` components calling the FastAPI backend on its
own origin (`NEXT_PUBLIC_API_URL`), a separate origin from the Next.js app in production. This
means the Next app's own HTML/RSC/static output carries **zero user-scoped data** — it is safe to
precache and cache without any purge concern. Only two request classes carry user data: calls to
the backend API, and signed photo URLs (a third origin — Supabase Storage).

### The five route classes

| # | Class | Strategy | Cache name | Purged at sign-out |
|---|---|---|---|---|
| 1 | App shell (same-origin: navigation, static assets, fonts, manifest) | `@serwist/next/worker`'s `defaultCache` (Next-aware precache + runtime rules) | Serwist/Workbox defaults | No — no user data (see above) |
| 2 | Backend API reads (`GET` to the API origin) | `NetworkFirst`, 4s timeout | `wtw-api-data` | **Yes** |
| 3 | Backend API writes, **including `POST /recommend/messages`** | `NetworkOnly`, explicit rule (not left to unmatched-passthrough) | nothing stored | n/a |
| 4 | Signed photo images (Supabase Storage origin) | `CacheFirst` + `ExpirationPlugin({ maxAgeSeconds: 3600 })` matching `wtw_photo_signed_url_ttl_seconds`. `CacheableResponsePlugin({ statuses: [200] })` — **not `[0, 200]`**, see "Amendment" below | `wtw-photos` | **Yes** |
| 5 | Reference data (`GET /taxonomy/categories`) | Folded into class 2 — same strategy, same cache, purged along with it | `wtw-api-data` | Yes (accepted cost, not worth a sixth cache name at this data volume) |

**Why not one uniform strategy**: `NetworkFirst` for class 3 would let Workbox serve a *cached
POST response* on a repeat failure — exactly the double-billing risk the handoff calls out by
name. `NetworkFirst` for class 1's content-hashed, immutable static assets just re-fetches bytes a
`CacheFirst`-style precache already guarantees are correct. One strategy is wrong in two different
directions at once; the class table is the smaller amount of real complexity.

### Two defects found only by running it, not reading the config

The handoff's own recurring lesson ("check what actually happened, not that the call returned")
caught two real bugs while writing `e2e-pwa/service-worker-smoke.spec.ts` — neither visible from
reading `sw.ts` in isolation:

1. **`proxy.ts`'s auth middleware redirected `/sw.js` itself.** Its matcher excluded
   `_next/static`, `_next/image`, `favicon.ico`, `manifest.webmanifest` and a handful of image
   extensions, but not `sw.js`/`workbox-*.js`/`swe-worker-*.js`. Registering the service worker
   from a signed-out route (`/signin` — the SW must work pre-auth too, not just once signed in)
   hit the "redirect to `/signin`" branch, and browsers refuse to install a service worker whose
   script response is itself a redirect (`SecurityError`). Fixed by adding those three patterns to
   the matcher's negative lookahead.
2. **`CacheFirst` silently never cached photos.** `ItemPhoto`'s `<img>` has no `crossorigin`
   attribute, so a cross-origin request to Supabase Storage is made `no-cors` — the response the
   service worker's fetch handler receives is opaque (`status 0`). Serwist's `NetworkFirst`
   auto-allows this via a plugin its own constructor prepends; `CacheFirst` has no constructor of
   its own and inherits the base `Strategy`, which without an explicit `cacheWillUpdate` plugin
   only accepts exactly `status === 200`. Every photo request was returning 200 on the wire while
   `wtw-photos` stayed permanently empty — no error, no warning surfaced to application code, only
   visible by asserting real `caches.keys()` contents. Fixed with an explicit
   `CacheableResponsePlugin({ statuses: [0, 200] })` in class 4's plugin list, ahead of the
   `ExpirationPlugin`. **This fix's own conclusion is now partly superseded — see "Amendment"
   below, found in the next round of review.**

Neither would have been caught by a review of `sw.ts`'s config alone, or by unit-testing the route
table's matcher logic — both required an actual browser, an actual service worker, and an actual
inspection of `Cache` contents, exactly the "verify what is actually cached" instruction the
handoff repeats twice.

### Amendment (found in review after merge-readiness, before merge): opaque responses hid real failures too

**Status: decided, supersedes part of item 2 above.** `statuses: [0, 200]` fixed photos not
caching at all, but introduced a defect of its own, found in a later review pass: an opaque
response's `status` reads `0` **regardless of the real HTTP status** — a `no-cors` request cannot
tell the requester whether the underlying response was a 200 or a 500, by design (that is what
"opaque" means). `CacheableResponsePlugin({ statuses: [0, 200] })` therefore could not distinguish
a real photo from a transient failure and cached both identically. Proven: a photo URL made to
fail once with a 500, then healthy forever after, was stored in `wtw-photos` as
`type=opaque status=0` on the very first (failing) request; every subsequent visit — including
ones long after the same signed URL had recovered — served that cached failure from `CacheFirst`
with **zero** network requests, rendering `NoPhoto` for a URL that was perfectly valid.

**Fix, both halves required together:**
1. `ItemPhoto`'s `<img>` now carries `crossOrigin="anonymous"` — Supabase Storage sends
   `Access-Control-Allow-Origin: *` on every response, success or error alike (verified, including
   on a 400), so this doesn't change what loads, only what the browser is willing to report about
   the response: it becomes a real, readable `type: "cors"` response instead of an opaque one.
2. Class 4's plugin list is tightened to `CacheableResponsePlugin({ statuses: [200] })` — now that
   the response is real, the plugin can actually see a 500 and correctly refuse to cache it.

**Why both halves are required, not either alone:** `crossOrigin` alone, leaving `statuses: [0,
200]` in place, fixes the common case (a real HTTP 500 becomes a readable `status: 500` response,
which `[0, 200]` already correctly rejects) but leaves the `0` branch live for the case a
`crossOrigin` request can still legitimately produce a bare network-level failure with no real HTTP
response at all (DNS failure, connection refused, a rejected CORS preflight) — that residual `0`
would still be cached as if it were a photo, just a narrower window than before. `statuses: [200]`
alone, without `crossOrigin`, reverts straight to the original item-2 defect: every response stays
opaque (`status 0`) regardless of the real outcome, `[200]` never matches anything, and
`wtw-photos` goes back to staying permanently empty. Only both together close the gap.

**Regression test**: `e2e-pwa/photo-failure-recovery.spec.ts` — fails a photo once, then serves it
successfully, and asserts the second load actually reaches the network and recovers (not served
from a cached failure), plus asserts the cache's own entry is `status: 200, type: "cors"`, never
`status: 0`.

### Signed photo URLs: the fix is client-side, not a caching trick

A signed URL doesn't announce its own expiry to an HTTP cache — from the service worker's
perspective it's just a URL, indistinguishable from a live one until Storage answers 400. Rather
than try to detect "expired" inside `sw.ts` (would require decoding Supabase's signed-URL format,
coupling the worker to a storage implementation detail), `ItemPhoto.tsx` — the single component
every photo render funnels through (`ClosetGrid`, `OutfitsGrid`, both detail pages,
`ItemThumbnailRow` — verified, none render a raw `<img>` themselves) — gets an `onError` handler
that swaps to the existing `NoPhoto` placeholder, the same one already used when `src` is falsy.
This is correct regardless of *why* the image failed (expired token, Storage briefly down, object
deleted), which a cache-layer fix can't say.

### Sign-out purge

`caches.delete("wtw-api-data")` and `caches.delete("wtw-photos")` — by name, from the page (the
`CacheStorage` API is available on `window`, no message-passing to the service worker needed) —
run before navigating to `/signin`, via one shared `signOutAndClearCache()` helper used at both
existing sign-out call sites (`app/(app)/profile/page.tsx`, `components/auth/
ResetPasswordForm.tsx`). Deliberately **not** "delete every cache": that would also wipe class 1's
precache, leaving the next offline cold start on that device with nothing to render — the app
shell has no user data in it, so there is nothing to protect by purging it, and purging it anyway
would trade a real privacy win for a false one plus a real regression.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — five-class table + named-cache sign-out purge + client-side `onError` fallback | — |
| (b) Uniform `NetworkFirst` everywhere | Wrong for the billed POST (double-charge risk) and wasteful for immutable static assets. |
| (c) `StaleWhileRevalidate` for photos | A signed URL's bytes never change for that exact URL; revalidating re-fetches identical bytes. A changed photo gets a **new** URL from the JSON anyway, so the old entry is superseded, not stale. |
| (d) Detect signed-URL expiry inside the service worker | Requires decoding Supabase's URL format or an extra network call to check — more fragile than just handling the `<img>` element's own `error` event where the browser already reports the failure. |
| (e) `caches.keys()` + delete everything at sign-out | Also deletes the app-shell precache (no user data, doesn't need purging) and regresses the next offline cold start on that device until a new service-worker install/activate cycle repopulates it. |
| (f) Split taxonomy (class 5) into its own non-purged cache | Correct in principle, not worth a sixth cache name for one small reference list at this app's current scale. |

## 53. Feature 014 (Offline, caching and the update prompt) — update detection, and draft copy pending design-owner review

**Status: partially decided; copy is a draft, not final.** The handoff named this the slice's
second named decision (§3.2) and pointed at §51 as the precedent for how to handle UI copy with no
design-system entry. Full reasoning: `specs/014-offline-and-updates/research.md` R7–R8.

### Detection: reload-triggered only

Resolved via `/speckit-clarify` (2026-08-05), asked directly of the design owner: the app does
**not** poll for a new service worker in the foreground (no `setInterval` + `registration.update()`)
and does **not** attach a `visibilitychange` listener. Detection happens on the client's next real
navigation (full reload, back-navigation to a fresh document load, reopening the installed app) —
the browser's own navigation-time service-worker byte-check does the work; the app's job is only to
notice the result (`registration.waiting`, or an `updatefound` → `installed` transition completing
during that same navigation) and show the toast. `skipWaiting: false` (Serwist's default, not
overridden) is what makes this possible — an installed-but-not-yet-active worker sits in `waiting`
rather than taking over unasked. Dismissing the toast needs no persisted flag: since nothing
re-checks mid-session, plain component state (reset by the next real navigation) is enough — there
is no other event during the same page life that would justify bringing it back.

### Why this is not §51's exception

§51 carved out an exception to Principle VIII for copy that is *itself a response to unpredictable
user input* (the five model-written conversational-turn lines) — a fixed string there would have
been the canned-reply failure mode §37 exists to remove. The update-prompt toast is not that: it is
one fixed system message that fires in exactly one circumstance, closer in kind to the offline
banner ("You're offline…") than to a conversational reply. §51's exception does not apply here —
this is ordinary Principle VIII copy that simply has no design-system entry yet, handled the
ordinary way: drafted, flagged, and routed for review, not treated as licensed to write in code.

### Draft copy (pending design-owner sign-off)

Kept in exactly one file, `frontend/lib/pwa/updateToastCopy.ts`, marked as a draft in a comment a
reader can't miss:

| Element | Draft text |
|---|---|
| Body | "A new version is ready." |
| Action button | "Update now" |
| Dismiss | icon-only close control (existing `IconButton icon="close"`), `aria-label="Dismiss"` |

Voice: impersonal/system register, per `design-system.md` §9's explicit exception for
connection/sync copy ("stays impersonal because it's describing device/network state, not a
styling decision") — matching the offline banner's own register, not the first-person-stylist
voice used elsewhere. **This is a draft, not final copy** — swap it for the design owner's actual
wording once given, in that one file, and remove the draft flag comment when it's real.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — reload-triggered detection, draft-and-flag copy | — |
| (b) Poll + visibility-triggered detection (the more "robust" industry-standard combination) | Explicitly declined when asked directly — the design owner chose the simpler reload-triggered behavior over proactive detection while a tab stays open. |
| (c) Toast reappears on next in-app navigation after a dismiss | Doesn't fit reload-triggered detection: in-app (client-side) navigation never re-checks the service worker, so there is no new information to justify re-showing it before the next real reload. |
| (d) Treat this like §51's exception and let a model draft the copy per-occurrence | Wrong category of copy — this is one fixed system message, not a reply to unpredictable input; §51's own "What this does not license" section says as much. |

## 54. Feature 017 (Deployment readiness) — CORS origins configuration

**Status: decided.** CORS allowlist is configured via the `wtw_cors_origins` environment variable, parsed through the `Settings` class (not bare `os.getenv` at module level).

### Default and parsing

- **Development (default):** If `wtw_cors_origins` is unset or empty, defaults to `["http://localhost:3000", "http://localhost:3100", "http://127.0.0.1:3000", "http://127.0.0.1:3100"]`.
- **Staging/production:** Set to a comma-separated list (e.g., `https://app.example.com,https://staging.example.com`).
- **Parsing:** Each origin is `.strip()`'d of leading/trailing whitespace; empty entries are filtered. A string of only commas and whitespace reverts to defaults.

This prevents the silent failure mode where `"https://app.example.com, https://staging.example.com"` (note the leading space on the second origin) passes configuration validation but the second origin is never matched — the space becomes part of the origin string, no browser's `Origin` header includes it, and requests from that origin are silently rejected.

### Amendment (found in review, before merge): the variable was inert, and this section's own reasoning is why

**Status: supersedes the "Why Settings, not bare os.getenv" argument originally recorded
here.** As first implemented, `wtw_cors_origins` and its six unit tests existed, and
`render.yaml` set `WTW_CORS_ORIGINS` — but `main.py` still passed a hardcoded localhost
list to `CORSMiddleware`. **Nothing read the parsed value.** Every request from a
deployed frontend would have been rejected by CORS.

The sequence that produced it is worth recording, because the reasoning looked sound at
each step:

1. `allow_origins=get_settings().cors_allowed_origins` was wired in, correctly.
2. That broke `test_import_safety.py` — `Settings` requires `DATABASE_URL`, middleware
   registers at import time, and `whattowear.main` is named in that test's module list.
3. The conflict was resolved by reverting to the hardcoded list, leaving the mechanism
   in place but disconnected.

Step 3 is the error, and this section's original claim — that bare `os.getenv` "breaks
the import-safety contract" — is what made it look like the only option. **It does not.**
`os.getenv` returns `None` for a missing variable; it never raises. The contract forbids
*requiring configuration at import*, not *reading the environment at import*.

**Resolution:** parsing moved to a module-level pure function,
`core.config.parse_cors_origins(raw: str | None)`. `main.py` calls
`parse_cors_origins(os.getenv("WTW_CORS_ORIGINS"))` — no `Settings`, contract intact —
and `Settings.cors_allowed_origins` delegates to the same function for any caller that
does hold a `Settings`. One parser, two entry points, no possible drift.

**Why no test caught it:** `test_config.py` exercised the parser in isolation, and every
test in `test_cors.py` used a localhost origin — which is allowed whether the wiring
exists or not. Green suite, broken deployment. This is the fifth defect on this project
with the identical shape: *a value is accepted, then silently dropped before it is used.*

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — module-level `parse_cors_origins()`, called from `main.py` via `os.getenv` and from `Settings.cors_allowed_origins` | — |
| (b) `get_settings()` in `main.py` | Genuinely breaks the zero-env-vars import contract; this part of the original reasoning was right. |
| (c) `Settings` field with no call site in `main.py` | What shipped and was reverted — the mechanism exists and does nothing. |
| (d) App factory (`create_app()` + `uvicorn --factory`) | Clean, and would allow `get_settings()` — but changes the ASGI target referenced by the Dockerfile, CI, the e2e config and every `TestClient(app)` import. Disproportionate to the problem. |
| (e) Duplicating the parsing inline in `main.py` | Two implementations of the stripping rules, free to diverge — the failure this section already exists to prevent. |

### Test coverage

`tests/unit/test_config.py` covers the parser: unset, whitespace stripping, empty-entry
filtering, whitespace-only and empty-string input.

`tests/integration/test_cors.py::test_a_configured_deployment_origin_is_allowed` covers
the **wiring** — that a configured origin reaches the running app, that an entry
following a comma-space is matched, and that configuring origins *replaces* the local
defaults rather than extending them. Verified to fail against the hardcoded list and
pass against the fix.

---

## 55. Feature 017 (Deployment readiness) — Checkpointer initialization modes

**Status: decided.** Checkpointer initialization is controlled by the `wtw_checkpointer_mode` setting ("auto" | "memory" | "postgres"), preventing silent fallback to RAM when a cloud service misconfigures or forgets `DATABASE_URL`.

### Three modes

- **"auto" (default):** Use Postgres if `DATABASE_URL` is reachable; otherwise use `InMemorySaver`. Suitable for local development with or without Postgres.
- **"memory":** Explicitly use `InMemorySaver` (development, testing, or deployments that don't need persistence).
- **"postgres":** `DATABASE_URL` must be set and reachable; fail at boot if missing (catches misconfiguration on cloud services).

### The problem solved

When `DATABASE_URL` is unset on a cloud service, the original code silently used `InMemorySaver`, and everything appeared to work until the first pod restart — then all active conversation threads vanished from RAM without warning. This is a load-bearing failure: conversations are the app's primary state, and losing them silently is worse than failing loudly at boot.

The fix requires an **explicit signal** to distinguish:
- Local development with no Postgres (valid, intentional, common) → "auto" or "memory"
- Staging/production where DATABASE_URL was forgotten (misconfiguration, dangerous) → "postgres" mode + error at boot

### Why not just raise when `DATABASE_URL` is missing?

Local development often runs without Postgres (Supabase, checkpointer, and knowledge base can be optional depending on what you're testing). The `"auto"` default preserves that capability while `"postgres"` mode catches cloud misconfiguration.

**Rejected alternatives:**
- **(a) chosen** — Three-mode system with "auto" default — Backward compatible, explicit signal for prod, silent fallback still works locally.
- (b) Always require `DATABASE_URL` — Breaks local dev; doesn't distinguish intentional (memory mode) from misconfiguration (forgot the env var).
- (c) Environment-specific detection (check if `ENVIRONMENT=staging` to decide whether to fail) — Assumes the environment setting is correct, which is the same problem we're trying to catch.
- (d) Add a separate `REQUIRE_POSTGRES` boolean — Redundant with the three modes; less clear than a named mode.

### Test coverage

`tests/unit/test_checkpointer_init.py` covers: memory mode (always InMemorySaver), auto mode with no DB (falls back to InMemory), postgres mode with no DB (raises RuntimeError), invalid mode (raises ValueError), and singleton behavior.

---

## 56. Feature 017 (Deployment readiness) — Docker image build strategy

**Status: decided.** Docker image builds use `uv sync --frozen --no-dev` for reproducible, pinned dependency installation from `uv.lock`. `.dockerignore` explicitly excludes secrets (`.env`, `legacy.env`), large build artifacts (`.venv`, `evals/`), and development files.

### Reproducibility and security

- **`uv sync --frozen --no-dev`:** Installs exact versions from `uv.lock` (not `uv pip install -e .`, which ignores the lockfile and rebuilds from `pyproject.toml`). Guarantees every build is identical.
- **`.dockerignore` exclusions:**
  - `.env` and `legacy.env` — secrets never baked into images
  - `.venv/` (531 MB) — no sense shipping the host's virtualenv; the image gets its own
  - `evals/` (698 MB) — evaluation datasets not needed at runtime
  - `.git/`, `__pycache__/`, `.pytest_cache/` — not needed at runtime
  
Without `.dockerignore`, the build context was ~1.2 GB (mostly `.venv` and `evals/`), and secrets were copied directly into the image layers.

### Non-root user and $PORT

The Dockerfile runs the app as a non-root user (`appuser`, UID 1000) for security. The `$PORT` environment variable is respected at runtime (defaults to `8000`), allowing hosting platforms (Render, Cloud Run) to inject their own port.

**Rejected alternatives:**
- **(a) chosen** — uv sync --frozen, .dockerignore, non-root user, $PORT env var — Production-ready, secure, reproducible, platform-flexible.
- (b) `uv pip install -e .` — Ignores uv.lock; not reproducible.
- (c) Hardcoded port 8000 in CMD — Inflexible; standard platforms inject PORT.
- (d) Run as root — Security risk; Render and other platforms default to non-root anyway.

### Image size

Final image is ~1.27 GB (Python 3.12 slim + FastAPI + LangChain + Qdrant client). This is reasonable for this dependency footprint; optimization opportunities (e.g., multi-stage build, Debian packaging) are deferred.

---

## 57. Feature 017 (Deployment readiness) — Hosting plan and cold-start tradeoff

**Status: decided.** Backend is deployed on Render's **free tier** (`plan: free`), accepting cold-start downtime in exchange for zero cost during development/staging.

### The cold-start cost

Render's free tier spins down on inactivity. A cold start means:
1. Container spins up (takes 10-30 seconds typically)
2. Python boots (instantiates uv dependencies)
3. App startup runs (calls `get_engine()`, `get_compiled_graph()`, `PostgresSaver.setup()`, checkpointer RLS hardening)

Total: ~20-60 seconds before the first request is answered. This is visible to the user.

### Staging: acceptable. Production: not.

**Staging/testing:** Free tier is fine. Infrequent requests, tolerable latency.

**Production:** Should upgrade to Render's paid tier or an equivalent always-on service. Cold starts on user-facing endpoints are unacceptable.

The `render.yaml` currently specifies `plan: free`. When moving to production, change this to `plan: starter` (~$7/month) or higher to eliminate cold starts.

**Rejected alternatives:**
- **(a) chosen** — Free tier for staging, cost upgrade for prod — Covers both use cases correctly without premature spending.
- (b) Paid tier always — Wastes money during development.
- (c) Serverless (e.g., Cloud Run) — Different cold-start behavior; still slow for the LLM bootstrap. Revisit if scaling demands it.

---

## 58. Feature 017 (Deployment readiness) — corrections found in review

**Status: decided.** Four defects found reviewing 017 before merge, each verified by
running it rather than reading it. Recorded together because they share a cause: config
that is *written* is not config that is *in effect*, and none of these were observable
from the source alone.

### 58.1 `render.yaml` — `scope: "secret"` is not a Render field

Six variables were marked `scope: "secret"`, which Render does not recognise on an env
var; it makes nothing secret and may fail blueprint validation. Render's actual
mechanism is `sync: false` — "prompt me in the dashboard, never store this in git."
Corrected, and `WTW_CORS_ORIGINS` moved to `sync: false` as well: the real Vercel URL
isn't known until the frontend deploys, and a guessed value silently rejects every API
call from the actual one.

### 58.2 `render.yaml` — no `branch`, so Render would have deployed the legacy app

`rebuild` is not this repository's default branch; `main` still is, and `main` is the
legacy prototype. A blueprint with no `branch:` deploys the default branch — so Render
would have built the old application from a blueprint written for the new one, with the
new environment variables. Pinned `branch: rebuild`, with a note to change it at cutover.

**Amended 2026-08-08 — cutover happened.** `main` is now the rebuild and the default
branch; `branch: main` is pinned instead. The paragraph above is left as written because
it records why the line existed, which is still the reason it is pinned at all rather
than left to default. The prototype is preserved at the `prototype-final` tag and on
`legacy-main`, neither of which is deployed.

### 58.3 `render.yaml` — `dockerfilePath` doubled the path, and `PORT` was overridden

`rootDir: backend` sets the build context, and `dockerfilePath` resolves relative to it —
so `./backend/Dockerfile` looks for `backend/backend/Dockerfile`. Corrected to
`./Dockerfile`.

`PORT` was also pinned to `8000` in `envVars`. Render injects its own `PORT` and
health-checks the port it assigned; overriding it makes the service listen where the
platform is not looking. Removed — the Dockerfile's `ENV PORT=8000` remains as a default
for local `docker run`, and the CMD reads `${PORT}` at container start either way.

### 58.4 The image was ~500 MB larger than it needed to be

`RUN useradd && chown -R appuser:appuser /app`, placed after the dependency install,
rewrites every file it touches into a new image layer — so the ~500 MB dependency tree
was stored twice. Measured: **1.27 GB**, with 68 s spent in the chown step alone.

Creating the user first, chowning `/app` while it is still empty, and using
`COPY --chown` gives an identical result with no duplicate layer: **776 MB**, and build
time down from 1m43s to 39s. `tests/`, `.ruff_cache/` and `.import_linter_cache/` were
also added to `.dockerignore` — none are needed at runtime.

`/app` must be chowned explicitly before `WORKDIR`: `WORKDIR` creates the directory
root-owned, and `COPY --chown` sets ownership on the files it copies, not on the
directory containing them, so `uv venv` fails with `Permission denied` without it.
Found by building, not by reading.

### 58.5 The runbook would have produced a broken Supabase project

The runbook is what the repo owner follows without a developer present, so its errors
are the most expensive kind. Corrected:

| Wrong | Actual |
|---|---|
| Migrations in `backend/migrations/`, named `0001.sql` | `infra/supabase/migrations/`, named `0001_init.sql` … `0012_conversational_turns.sql`. `backend/migrations/` does not exist, and the documented `printf "%04d"` loop matched nothing. |
| Storage bucket named `photos` | **`wardrobe-photos`** — hardcoded in `0006_wardrobe_photos.sql`'s RLS policy and in every signed URL. Any other name leaves uploads 404ing while the app looks fine. |
| Create bucket RLS policies by hand | `0006_wardrobe_photos.sql` already creates `wardrobe_photos_owner_rw` and its grant. The hand-written SQL given was not valid policy syntax and cited a `0013_storage_rls.sql` that does not exist. Replaced with a verification query. |
| `DATABASE_URL` shaped like `postgres.pooler-dev@db.<ref>.supabase.co:6543` | That username is the **local** Supabase CLI's pooler emulation. A hosted project's pooler host and username differ; the runbook now says to copy the string from the dashboard rather than hand-write it. |

Also added: `supabase db push` as the primary migration path (the repo is already set up
for it), `ON_ERROR_STOP=1` on the psql fallback so a failure cannot leave a half-applied
schema, and a note that `DATABASE_URL_DIRECT` is best left unset on Render — Supabase's
direct connection is IPv6-only without the IPv4 add-on, and the checkpointer already
falls back to the pooler.

---
## 59. Feature 017 (Deployment readiness) — the knowledge base on a host without the corpus

**Status: decided.** Found on the first real staging deploy: the first styling request
returned 500 from `pipeline/graph.py`'s `style_retrieval` node —

```
File "/app/src/whattowear/kb.py", line 40, in get_kb
    raise RuntimeError: CORPUS_LOCAL_DIR is required to build/reconnect to the
    knowledge base.
```

### Why a deployed instance could never satisfy that

`CORPUS_LOCAL_DIR` points at `../../w2w-corpus` — a directory **outside the repository**.
The corpus is deliberately not in git (Principle X treats documents as data; the eval
fixtures under `evals/fixtures/` are called out as the one exception), and the Docker
build context is `backend/`, so it is not in the image either.

The non-obvious part is that this blocked *reconnecting*, not just building.
`get_kb()` called `ingest_all(corpus_dir)` unconditionally, before deciding whether to
re-embed, because it needs `len(chunks)` for the stale-corpus freshness check **and**
because `KnowledgeBase.chunks` is itself load-bearing: `retrieval/hybrid.py` reads
`kb.by_layer("L4")` and `kb.by_layer("L1")` directly off the raw chunks rather than
through the vectorstore. So even a fully-populated Qdrant collection was unusable without
the source documents on disk.

### Resolution — `WTW_KB_MODE`

| Mode | Behaviour |
|---|---|
| `corpus` | Read `CORPUS_LOCAL_DIR`, then build or reconnect. **The original, evaluated path, unchanged.** |
| `reconnect` | Attach to an existing Qdrant collection; rebuild `chunks` by scrolling the stored payloads. Never reads the corpus. |
| `auto` (default) | Same as `corpus`. **Does not** fall back to `reconnect` — see the correction below. |

`QdrantVectorStore.from_documents` writes each Document under langchain-qdrant's default
payload keys (`page_content`, `metadata`) — verified by scrolling a real point from the
staging collection before the code was written, not assumed from the library's defaults.
The metadata carries `layer`, `rule_id` and `granularity`, so `by_layer()` works
identically on reconstructed chunks.

## 60. UI conformance batch (issue #33) — Add Item photo aspect ratio

**Status: decided.** `design-system.md`'s "Image treatment" table documents the Add-item
review-card photo (and, by the same rule, the scanning/upload-error states added later) as
"full-width, fixed height: 150px... same flexing behavior [as the hero photo/dropzone]" —
written when "no real photos exist in the prototype... every photo is the same
diagonal-stripe placeholder" with no real aspect-ratio concerns. Real uploaded photos expose
the problem a fixed-height `object-fit: cover` box can't avoid: a portrait photo gets
cropped down to a sliver of its actual content.

### Resolution

Read the photo's own `naturalWidth`/`naturalHeight` on load (CSS alone can't branch on an
image's intrinsic aspect ratio) and treat orientation as the deciding factor, not a fixed box:

| Orientation | Treatment |
|---|---|
| Landscape or square (`width >= height`) | Natural aspect ratio, full width, no cropping |
| Portrait (`height > width`) | Centered in a square (`aspect-ratio: 1`, `object-fit: contain`), full container width — letterboxed with empty space left/right, never cropped. Deliberately **not** Closet grid tile's treatment, which crops via `object-fit: cover` — the whole garment staying visible mattered more here than filling the box. |

Implemented once as `frontend/app/(app)/add/OrientationAwarePhoto.tsx`, replacing five
separate call sites that had each duplicated the same fixed-150px-height rule
(`ReviewCard.tsx`, `AddItemFlow.tsx`'s scanning and empty states, `BulkQueue.tsx`'s scanning
and upload-error states). Defaults to the square treatment before the image loads, rather
than collapsing to zero height — orientation is briefly unknown, and local blob URLs (the
only source this ever renders) load fast enough that the window isn't visually significant.

Verified against the real staging cluster with `CORPUS_LOCAL_DIR` unset: 391 chunks
rebuilt from 391 points, `by_layer("L1")` → 197, `by_layer("L4")` → 65, L1-atomic → 15,
and a live `similarity_search` through the gateway returning correctly ranked results.

### Correction (2026-08-08): `auto` briefly fell back to `reconnect`, and that was wrong

As first written, `auto` reconnected whenever `CORPUS_LOCAL_DIR` was unset. That is a
silent fallback of exactly the kind this section's next heading argues against, and it
shipped anyway.

The consequence: a local process with no corpus configured would quietly attach to
whatever collection its Qdrant settings pointed at — in practice the deployed one — and
serve it as if it had built the knowledge base itself. No error, no warning, someone
else's knowledge base.

It was caught by `tests/unit/test_kb.py`'s pre-existing contract test, which had asserted
since feature 007 that a missing `CORPUS_LOCAL_DIR` raises. That test was not run when
the change was made — only the new `test_kb_modes.py` was — and the full-suite run that
did cover it passed only because that machine's Qdrant had no matching collection at the
time. The bug was therefore invisible until the same suite ran against a populated cloud
cluster.

Two lessons worth keeping: **a new test file does not replace the module's existing one**,
and a passing suite proves less than it appears when behaviour depends on reachable
external state.

`auto` now means `corpus`. Reconnecting reads a collection the process cannot verify
against the corpus that produced it, so it is an operational choice and must be asked
for. `render.yaml` sets `WTW_KB_MODE=reconnect` explicitly, which was always the intent.

### Every reconnect failure is loud

Missing URL, missing collection, and empty collection all raise, with a message naming
the fix. This is the `wtw_checkpointer_mode` lesson (§55) applied again, and it matters
more here: an empty knowledge base does not crash. Retrieval simply returns nothing, and
styling produces ungrounded output — a Principle IV violation that looks like working
software. Silence is the dangerous outcome, so it is the one that is forbidden.

The `corpus`-mode error message now also names `WTW_KB_MODE=reconnect`. The original text
named only `CORPUS_LOCAL_DIR`, which is unactionable advice on a host that will never have
the corpus — it is what sent this investigation toward "set the variable" instead of
"this host cannot have the file".

### Constitution note

The KB is evaluated code, and the constitution requires an eval run for any refactor of
it. The `corpus` branch is byte-for-byte unchanged and remains the default wherever a
corpus is configured, so the evaluated path is untouched by construction; the new branch
is reachable only by explicit opt-in. Initial verification here was a single live
reconnect + retrieval check (recorded above), deferred until staging was working end to
end.

**Closed 2026-08-11 — `docs/eval-baselines/017-kb-reconnect/`.** Full golden set (24
cases), all three strategies, `corpus` mode vs `reconnect` mode run back-to-back on the
same day, same corpus, same Qdrant collection. `retrieval_recall` — the one metric that
depends purely on KB content — was **byte-identical between the two modes across every
strategy** (0.79 / 0.94 / 0.94 baseline/hybrid/advanced, both runs), and matches the
last recorded `advanced`/`grounded` baseline (`010-engine`, 2026-07-31: 0.94).
`owned_only`, `cites_grounded`, `every_choice_cites`, `occasion_fit`,
`respects_exclusions`, `all_have_four_scores` and `ranked_descending` were `1.00` in
both runs, every strategy. See `COMPARISON.md` in that directory for the full table and
the generation-dependent metrics' expected run-to-run drift. The eval run this section
named as outstanding is done; §59 is settled.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — `WTW_KB_MODE`, chunks rebuilt from Qdrant payloads | — |
| (b) Ship the corpus into the image | Reverses a deliberate Principle X decision, and grows the image by the whole corpus for data Qdrant already holds. |
| (c) Let retrieval degrade when the KB is unavailable | Constitution III makes style knowledge gate retrieval; silently ungrounded output is the failure Principle IV exists to prevent. |
| (d) Persist the chunk list as a build artifact alongside the image | A second copy of the same data, free to drift from the collection it describes. |
| (e) Have the deployed instance ingest on boot | Needs the corpus (which it does not have), re-embeds on every cold start, and on Render's free tier that is every ~15 idle minutes. |

---

## 61. Feature 020 (Calendar pick reaches Recommend) — what a picked event does to the conversation

**Status: decided.** GitHub issue #41, defect 3: `recommend.py` never reads a user's picked
event, so picking one today changes a label and nothing else. This section settles what
"seed the conversation" means before any pipeline code was touched, per the issue's own
instruction not to shortcut past it.

### The three options, weighed

**(a) Silent full pre-fill.** Read the picked event and write `occasion` (from the title),
`formality` (via `context_assembler.infer_formality(title)`), and `location` straight into
the graph checkpoint the moment a fresh thread starts, exactly as if the user had typed
them. This is the cheapest reading of "mostly wiring" — and it is rejected outright.
`infer_formality` maps free text to one of six formality values by keyword match
(`context_assembler.py`'s own `OCCASION_KEYWORDS`); "Dinner with Ana" contains no keyword
that table recognizes, so it would silently resolve to the `smart_casual` fallback and
present that guess to the scoring/rationale pipeline as though the user had stated it.
Constitution IV requires every rationale to cite retrieved principles or scorer output —
never a fabricated premise — and an unstated formality guess dressed as a fact is exactly
that fabrication, just moved one step earlier than a citation. This is the literal failure
mode the issue names and tells the implementer to stop and reconsider if they find
themselves about to build.

**(b) Seed a first assistant message.** Before any user turn exists, insert an
assistant-authored bubble — the issue's own example: *"Styling for Dinner with Ana, Friday
8pm — anything I should know?"* Rejected, for two independent reasons:

1. **Principle VIII.** `design-system.md` § Screen anatomy → Recommend, item 2 fully
   specifies the hero state's one assistant line as a fixed welcome bubble with fixed copy.
   There is no design-owner-approved copy for a second, dynamic, event-derived bubble, and
   §51 already establishes the boundary for when this codebase is allowed to let something
   other than a human-authored string appear as assistant copy: *only* the five conversational
   situations that are themselves a reply to unpredictable user input. A greeting authored
   before the user has said anything is not that — it is closer to the three Python-owned
   lines §51 keeps fixed, and none of those three were ever left to be invented per-feature
   without design review.
2. **Structural cost for a "mostly wiring" feature.** Every assistant line today is either
   `conversation.reply`'s per-turn LLM output or one of `copy.py`'s three fixed strings, and
   both only ever fire *after* a user turn creates the thread (`POST /recommend/turns`
   inserts the `user_message` row first, then produces the reply). An event-seeded opening
   line would be the first assistant-authored content with no preceding user turn anywhere
   in this codebase — a new shape, for a feature the issue explicitly frames as wiring, not
   new capability.

**(c) Split by reliability — the decision.** Location (and the weather/season context
`assemble_context` derives from it) is treated as fact and silently carried into the
conversation. Occasion/formality is never asserted — the event's title and time are offered
back to the user as their own editable, not-yet-sent text, requiring an explicit Send before
either reaches the pipeline.

Concretely:

- **Location — silent, deterministic slot seed.** The moment `POST /recommend/turns` opens a
  brand-new thread (`thread_id` absent from the request) for a user who has a picked event,
  the route calls `graph.update_state(config, {"location": event.location})` *before*
  `known_slots` is read and `conversation.reply` is called — the same checkpoint write
  `/recommend/turns` already performs after every turn's extraction, just seeded once,
  deterministically, with no LLM involved. Two consequences fall out of code that already
  exists (`recommend.py`'s existing `known_state.get(key)` loop, `context_assembler`'s
  existing `location` param and free `get_weather` call): the conversational model's own
  "already known" line (`conversation._known_slots_line`) already lists location, so the
  prompt itself steers the model away from re-asking it; and if "Start styling" is tapped
  before location comes up in conversation at all, `POST /recommend/messages`'s existing
  first-invoke branch still carries it through to `assemble_context`, so weather-aware output
  follows without any pipeline change.
- **Occasion/time — composer pre-fill, not assertion.** The Recommend screen's `Composer`
  gains an optional initial value. When the store's conversation is genuinely fresh (no
  thread yet, no messages — the same condition that shows the hero state) and a picked event
  exists, the input is pre-filled with a plain template of the event's own title and time
  (`"{title}, {relative day/time}"`, the same time formatting `EventRow` already renders) —
  fully editable, sending nothing until the user taps Send. No new component and no new
  chat-surface copy: the input box already exists: this uses it in an already-supported way
  (a non-empty initial value) rather than adding a bubble, a chip, or a confirmation dialog.
  It is deliberately **not** wired into the hero's three suggestion chips
  (`HeroState.tsx`'s `SUGGESTION_CHIPS`) — that row is `design-system.md`'s literal "row of 3
  suggestion chips" with named copy; changing its count or contents for a state the design
  system was never asked about is exactly the kind of invented visual Principle VIII forbids,
  where pre-filling the one form control that has never had specified content is not.

### Why occasion and location are not treated the same

The issue's own instruction: *"location and start time are reliable, occasion is not."*
Location is not an inference — it is the address the user put on their own calendar event,
structurally identical in trustworthiness to a user typing "I'm at Tanto" mid-conversation
(which `conversation.reply`'s extraction already writes to the same slot without
confirmation). Occasion-as-formality-signal is a real interpretive step:
`infer_formality` has to guess whether "Dinner with Ana" means a rooftop first date or a
work obligation, and those guesses produce different, contradictory scoring. The reliability
gap is exactly the line Constitution IV draws between "user data" and "stylist inference" —
so the two slots get different treatment on purpose, not the same wiring applied twice.

### What happens when the user's own words contradict the event

The event never gets special authority to defend. `location` seeded from the calendar and
`location` extracted from a later message live in the exact same graph-state key, written by
the exact same `graph.update_state(config, updates)` call `POST /recommend/turns` already
makes after every turn's extraction (`recommend.py`, the `updates` dict built from
`result.location`). A later turn that extracts a different location overwrites the seed the
same way it would overwrite anything said in an earlier turn — no new precedence code, no
"is this from a calendar or from the user" flag anywhere. The user always wins, by the
mechanism that already existed for correcting any other stated fact.

### Scope boundary: only a fresh thread

Both halves of (c) are gated on the conversation being new (`thread_id` absent /
`hasUserMessage` false). A picked event does not retroactively inject itself into an
already-running conversation — reaching Recommend mid-conversation with a newly picked event
still updates the "Styling for {event} · Change" label (defects 1/2), but leaves the
in-progress thread's own state alone. Rewriting live conversation state out from under an
in-progress exchange is a materially different, riskier feature than seeding a conversation
that has not started yet, and the issue's acceptance criteria describe only the latter.

### What this does not build

`design-system.md` §"Connected, has events" (all rows disabled once any event is picked,
opacity 0.5 / `cursor:not-allowed`) is unchanged — explicitly out of scope per the issue.
The only way back to an un-picked state remains disconnecting the calendar entirely
(`SupabaseCalendarRepository.disconnect` cascades `picked_events`); no dedicated "unpick"
affordance is added. The issue's acceptance criterion "a way to change/clear" is read as
preserving the existing "Styling for {event} · Change" link (already routes to `/calendar`,
untouched by this feature) — not as a request for new unpick UI, which nothing in
`design-system.md` specifies and which defects 1–3 do not require to be fixed. Recorded here
so it reads as a deliberate boundary, not an oversight.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(c) chosen** — location silently seeded as a deterministic slot; occasion/time offered as editable, unsent composer text | — |
| (a) Silent full pre-fill, including occasion/formality from the title | Constitution IV: presents a title-derived formality guess to the pipeline as though it were user-stated fact. The issue names this exact failure mode directly. |
| (b) Event seeds a first assistant-authored message | No design-owned copy exists for it (Principle VIII, §51's boundary); would be the first assistant line with no preceding user turn anywhere in the codebase, for a feature framed as wiring. |
| (d) Add the event as a 4th `HeroState` suggestion chip | Same tap-to-send mechanism as the composer pre-fill, but changes the hero's specified "row of 3" chip content for a case `design-system.md` never considered — smaller win than the composer pre-fill for a larger Principle VIII risk. |
| (e) Do nothing beyond making the existing label current (defects 1/2 only) | Leaves defect 3 — the actual subject of this issue's "desired" section — unresolved; the pick would remain a label with no effect on styling output. |

---

## 63. Bulk-add photo ceiling reduced from 20 to 10 (issue #61)

**Status: decided.** `MAX_BULK_PHOTOS` (`frontend/app/(app)/add/page.tsx`) drops from 20 to
10, amending the ceiling `specs/006-photo-upload-vision/research.md` §6's addendum set.

### Why the original 20 was reconsidered

20 was chosen to match `wtw_closet_page_size` — "one screenful," a borrowed precedent, not a
number derived from this flow's own cost. Two things that precedent didn't weigh: each queued
photo is a separate billed vision call, and the review queue is one-at-a-time with no way to
save progress and pause partway through. Twenty photos is both a real bill and a long
uninterruptible sitting.

### The number

10, the low end of the issue's requested 10–15 range. **This is the product owner's explicit
choice, not a measured one** — the issue asked for the number to come from timing a real review
queue, and that measurement was not run. Recorded here rather than silently presented as
derived, per the same "say what you actually did" standard the rest of this file holds to.

Chosen deliberately at the low end: a 10-item queue is finishable in one sitting without feeling
open-ended, and it's more conservative on cost than 15 while still comfortably above the original
decision's own rejected floor (5, called "overly restrictive").

### What last time's decision got right and still holds

The original addendum rejected *no limit* (unbounded full-resolution photos in browser memory,
each up to `wtw_max_upload_bytes`) and rejected *5* (too restrictive for cataloging a whole
wardrobe in one sitting). Both of those reasons are unaffected by this change — 10 still leaves
meaningful headroom above 5 for that same use case, just less than 20 did.

### Rejected

| Option | Rejected because |
|---|---|
| **(a) chosen** — 10 | — |
| (b) Measure real review-queue timing first, per the issue's own instruction | Correct as stated, but not run; the product owner made the call directly instead. Recorded honestly above rather than backfilled as if measured. |
| (c) 15, the top of the issue's range | Leaves the cost/session-length problem this issue exists to fix only partially addressed. |
| (d) Leave 20 | The issue's whole premise — this is a real bill and a long uninterruptible session — remains true at 20. |

## 64. Skip/cancel in the add-item flow (issue #62)

**Status: decided.** The issue names three gaps in one sentence — skip the current photo, or
cancel the batch — but they don't share a risk profile, and treating them identically was the
wrong instinct to check before writing any code.

### Skip the current photo: one tap, no confirmation, reused (not new) copy

Once a photo scans successfully into the `ready` review card, there was previously no way to
abandon just that item — the only forward path was Save. `BulkQueue.tsx` already had a skip
link, but it only rendered for `upload-error` (a photo whose upload itself failed, which can
never be saved). The issue's own note is explicit about what the *new* one should feel like:
"skipping should feel like the same deliberate, quiet behaviour rather than an error state" —
which reads directly as an instruction not to gate it behind a confirmation dialog. A confirm
step on every skip would make the quiet, low-stakes action (abandoning one photo, nothing
saved, nothing lost) feel as weighty as the batch-level cancel below, which is the wrong
signal to send for a single "not this one" decision the user can make dozens of times in one
sitting.

**Decision:** generalize the existing skip link to the `ready`/`save-error` states too — same
`.skipLink` style, same one-tap `advance()` call, disabled only while the current card's own
save request is in flight (so a skip can't race a save). The copy ("Skip this photo" / "Skip
and finish") is **reused verbatim**, not rewritten: it was already state-neutral (it never
said anything about an error), so the same pair of strings correctly covers both the recovery
case and the deliberate-pass case. It was hardcoded inline in `BulkQueue.tsx`; moved into
`lib/add-item-copy.ts` (`review.skipCta`) while doing this, matching how every other string on
this screen is owned.

**Rejected:**

| Option | Rejected because |
|---|---|
| **(a) chosen** — one-tap, no confirmation, existing copy reused | — |
| Confirm every skip ("Skip this item?") | Directly contradicts the issue's own "deliberate, quiet behaviour rather than an error state" instruction; would make routine, low-stakes browsing friction-heavy in a flow #61 just shortened specifically to reduce friction. |
| Write new copy for the ready-state skip, distinct from the error-state one | The existing string already doesn't reference an error — nothing about it needed to change for the new call site. Writing a second string for the identical action is exactly the "two skip affordances" failure mode flagged as a risk going in. |

### Cancel the whole batch: confirm only when it would silently discard something

`CloseAddOverlay`'s X previously closed unconditionally (`router.back()` / `/closet`, no
dialog). The issue names the real risk directly: a user five items into a ten-item batch,
several already saved, taps X and loses the rest with zero warning. But #61 (this same day)
shortened bulk batches specifically to reduce friction and make them finishable in one
sitting — so the fix here has to add exactly the friction the risk justifies, not more.

**Decision, single-item flow: never confirm.** Nothing is saved before the final Save tap
(`AddItemFlow`'s `onClose` only ever fires *after* a successful save), so there is nothing a
close can silently discard. A confirmation here would be pure friction with no corresponding
risk — `AddItemFlow.tsx` needed no code change for this issue at all (see "What I didn't
touch" below).

**Decision, bulk flow: confirm only once `savedCount > 0`.** Not "any progress" (e.g.
currentIndex > 0 from skips alone) — specifically *saved* progress, because that's the exact
harm the issue names: real, permanent closet writes the user might not realize they're about
to strand behind an unwarned close. A batch abandoned before anything saved (browsed the first
photo, decided not to bother) has nothing to lose and gets no dialog, matching the
single-item flow's own reasoning. `BulkQueue` reports `{ savedCount, total }` upward the same
way it already lifts `{ current, total }` for the position indicator (`onPositionChange` →
`onSaveProgressChange`, same shape of lift, not a second queue owner); `page.tsx` derives
whether `CloseAddOverlay` needs to confirm from `entry.mode === "bulk" && savedCount > 0`.

**Already-saved items are never touched by canceling.** The confirmation dialog's copy says so
explicitly ("already saved to your closet"), and the implementation backs it up: canceling
only stops the component tree from issuing any further `from-upload` requests and then
navigates away — it never calls `DELETE`, and the items already written are rows in the
database, unaffected by anything happening in a browser tab that's about to close. Verified in
`page.test.tsx`'s integration test by asserting the exact POST call count after a cancel (the
upfront extracts plus the one save that happened — never a delete, never an extra save for the
abandoned cards).

**Dialog implementation:** `CancelBatchDialog` (new), reusing §22.2's exact bespoke `<dialog>`
pattern (real `showModal()`, focus trap/restore, safe-area-aware bottom padding) the same way
§40 reused it for outfit delete — a third instance of an already-established pattern, not a
new component category. Not merged into a shared abstraction with `DeleteConfirmDialog`/
`DeleteOutfitDialog`: the constitution's "two concrete implementations or a measured problem"
bar is about introducing a *layer*, and this codebase's own precedent for this exact pattern is
copy-and-adjust per entity (§40 didn't unify with §22.2 either), not a shared component: two
existing instances is not evidence a third needs different treatment.

**Rejected:**

| Option | Rejected because |
|---|---|
| **(a) chosen** — confirm only in bulk mode once `savedCount > 0` | — |
| Never confirm, anywhere | The named risk is real, not hypothetical — GH issue #62 exists specifically because this was silent. |
| Always confirm on close, single-item included | Nothing is ever at stake in the single-item flow before the final Save tap; a dialog with no corresponding risk is friction with no benefit, and inconsistent with #61's own direction (fewer obstacles between opening the flow and finishing it). |
| Confirm in bulk mode based on `currentIndex > 0` (any progress, saved or skipped) | Overcounts the risk: a batch where every prior card was *skipped*, not saved, has nothing real to lose on cancel — warning anyway would be friction unconnected to actual stakes, and dilutes the signal for when a dialog is genuinely warranted. |
| Merge `CancelBatchDialog` into a new shared `ConfirmDialog` used by all three (this, closet-item delete, outfit delete) | Bigger diff than this issue needs, touches two files this issue has no other reason to change, and isn't how this codebase has handled the same shape of decision before (§40 copy-adjusted rather than unifying with §22.2). A future consolidation is plausible but is its own deliberate decision, not a side effect of this fix. |

### Copy: mostly reused, one new draft

Per Principle VIII, no UI copy is invented in code. Two different situations applied here:

- The skip copy already existed and needed no rewrite (see above) — not a Principle VIII
  question at all, just a relocation.
- The cancel-batch dialog's copy is genuinely new; `design-system.md` §6's Add item table has
  no entry for it. Following §53's precedent (`updateToastCopy.ts`) rather than §51's: this is
  not a reply to unpredictable user input (§51's own "What this does not license" section says
  its exception is specifically for that), so it's handled the ordinary way — **drafted,
  flagged, and kept in exactly one place** (`lib/add-item-copy.ts`, the `cancelBatch` key, with
  a comment a reader can't miss) pending design-owner sign-off. Register matches the existing
  bespoke Delete dialogs (short, direct: "Delete {name}?" / "This can't be undone.") rather
  than the first-person stylist voice used on Recommend, since this is an in-flow system
  confirmation, not an assistant line.

**Draft copy (pending design-owner sign-off):**

| Element | Draft text |
|---|---|
| Title | "Cancel this batch?" |
| Body | "{savedCount} of {total} items are already saved to your closet. The rest won't be added." |
| Confirm action | "Cancel batch" |
| Dismiss action | "Keep reviewing" |

### Where skip lives relative to Save & next

Directly below the review card, as a sibling of the `<form>` rather than inside it (so a tap
can never be mistaken for, or trigger, a submit) — the same position the pre-existing
upload-error skip already used, inside the same `.queue` flex column with its existing
`var(--space-lg)` gap. No new spacing or placement value was introduced; `design-system.md`'s
Add item section names the review card and its Save & next / Save to Closet actions but has
nothing to say about a skip control, so the existing in-code precedent is what settles it
(Principle VIII covers layout, not just copy).

### What I didn't touch

- **`AddItemFlow.tsx`:** no code change. Its single-item flow has no "skip the current photo"
  concept (there's only one photo, and skipping it is indistinguishable from canceling), and
  per the single-item cancel decision above, its `onClose` already only fires after a
  successful save — nothing new to guard.
- **No merge of the three bespoke confirmation dialogs** into a shared component — see the
  rejected-alternatives table above.

## 65. Weather shown in the wrap-up line, with an emoji (issue #67)

**Status: decided.** The emoji-per-condition mapping and its temp_band fallback are the
product owner's explicit, exact direction (issue #67) — recorded here, not re-derived.

### The situation

`context_assembler.assemble_context()` already resolves real weather (`temp_c`, `condition`,
`temp_band`) into every `Context`, and `SendMessageResponse` already carries `temp_c` on every
turn — none of it ever reached the user except as an accidental, unlabeled word-swap in the
outfit meta line (`_meta_line`, which prefers `condition` over formality when known, but only
on a thread's first message; a refinement turn never recomputes `condition`, so it silently
reverts to formality without saying why). §49 already established the wrap-up line
(`copy.wrap_up_text`) as the deterministic, Python-composed summary shown the moment "Start
styling" is tapped — the model extracts, Python composes, exactly the pattern this issue
extends rather than departs from.

### Decision: append a weather clause to `wrap_up_text` when `temp_c` is known, two independent emoji tables, layered

`wrap_up_text(occasion, formality, *, temp_c=None, condition=None, temp_band=None)` appends
`" — {emoji} {temp_c:g}°C."` to the existing occasion/formality sentence whenever `temp_c` is
not `None`. The emoji is chosen from whichever of two tables applies:

1. **`condition` known** (a thread's first invoke, weather was just looked up) — the condition
   table below.
2. **`condition` is `None` but `temp_band` is known** (a refinement invoke — `condition`
   doesn't survive a refinement today, `temp_band` does; see `context_assembler.py`) — the
   temp_band fallback table below.
3. **Neither known** — no weather clause at all; today's occasion/formality-only text,
   unchanged, byte-identical. Never a placeholder or an empty slot (same standard §49 already
   set for the formality-unknown case).

**Why two layers, not one:** `temp_band` is not a subset or a coarsening of `condition` —
they're independent signals the pipeline computes at different points (`condition` only from a
live weather lookup; `temp_band` from either that lookup or a bare `temp_c`), and only one of
the two given emoji sets is temperature-shaped at all. Falling back from condition to temp_band
mirrors exactly which of the two fields actually survives a refinement turn, so the fallback
layer exists because the data layer already has one.

**Condition → emoji** (`_CONDITION_EMOJI`, covers every string `external/weather.py`'s `_WMO`
table can produce):

| Condition | Emoji |
|---|---|
| clear | ☀️ |
| mostly clear | 🌤 |
| partly cloudy | 🌤 (reused — not meaningfully distinct from "mostly clear") |
| overcast | ☁️ |
| fog | ☁️ (reused — no fog emoji in the given set; closest available concept) |
| drizzle | 🌦 |
| rain | 🌧 |
| heavy rain | 🌩 |
| showers | 🌦 (reused, same as drizzle) |
| heavy showers | 🌧 (reused, same as rain) |
| snow | 🌨 |
| heavy snow | ❄️ |
| thunderstorm | ⛈ |

**`temp_band` → emoji** (`_TEMP_BAND_EMOJI`, fallback only — used when `condition` is `None`):

| temp_band | Emoji |
|---|---|
| freezing, cold | ❄️ |
| cool, mild | 🌤 |
| warm, hot | ☀️ |

**🌪 (tornado) is deliberately unused.** Nothing in `_WMO`'s condition set means tornado;
forcing it onto an unrelated condition would be worse than leaving it unused. It stays reserved
for a genuinely tornado-appropriate condition, if `_WMO` ever gets one — not assigned as a
"best guess" now.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — one weather clause on `wrap_up_text`, condition table then temp_band fallback | — |
| A new dedicated weather chip/badge UI element | The issue names this explicitly as a separate, later ask — this slice reuses an existing, already-deterministic, already-approved mechanism instead of introducing new UI. |
| Fix the outfit meta line's silent-drop-on-refinement quirk in the same slice | Explicitly out of scope per the issue; filed separately if worth fixing on its own. |
| Derive a single merged emoji table (temp_band values folded into the condition table) instead of two | `temp_band` and `condition` are different vocabularies describing different things (six bands vs. thirteen WMO-derived conditions) — merging them would mean picking, per band, one representative condition-flavored emoji that no actual condition produced, which is exactly the kind of invented mapping the product owner's exact table was meant to foreclose. |

## 66. Location resolves to weather more reliably — city extraction + geocoding fallback (issue #68)

**Status: decided.**

### The situation

Verifying #67 against real conversational turns surfaced why the weather clause it added often
never appears: `location` reaches `get_weather()` (`external/weather.py`) as raw free text from
two sources — the conversational extraction (`conversation.reply()`) and a picked calendar
event's own `location` field (Google's raw text, `adapters/google_calendar.py`) — and
`get_weather()` made exactly one geocoding attempt against the string as given. A full venue
address resolves as neither: confirmed live, `"Wedding hall, MQVP+X67, Tbilisi, Georgia"`
(exactly what the extraction produced, unprompted, for a real message naming that venue) returns
zero results from Open-Meteo's geocoder, while `"Tbilisi"` alone resolves fine. `condition`/
`temp_c` then never populate, `assemble_context()` degrades silently (by design — see
`context_assembler.py`'s own docstring), and #67's clause correctly shows nothing — the fix
worked, the input feeding it just never arrived.

### Decision: two independent, additive fixes — extraction is nudged toward a city, geocoding gets a coarsening fallback

Neither fix depends on the other; both are needed because they close different gaps upstream and
downstream of the same string.

1. **`prompts/conversational_turn_system.md` (v3 → v4):** a new instruction, alongside the
   existing formality-mapping rule, that `location` must be the city (plus region/country only
   to disambiguate), never a venue name or street address — with a worked example using the
   exact Tbilisi wedding-hall text this issue was found from. Verified live, same input:
   `location` now extracts as `"Tbilisi"`. This is an extraction-shaping instruction, not new
   user-facing copy, so it doesn't route through the design-owner review §63 established for
   this prompt's *voice* section — the same distinction the existing formality-mapping paragraph
   already relies on.
2. **`external/weather.py`'s new `_geocode()`:** on a miss, retries against progressively
   coarser comma-separated segments (dropping the left-most/most-specific one each time) before
   raising. A bare city (no comma) makes exactly one request, unchanged from before. This is the
   layer that also covers calendar-event locations, which have no LLM extraction step to fix
   them at the source.

Together: the prompt fix means most new free-text mentions never need the fallback at all: the
fallback is what catches everything the prompt can't reach — calendar events, and any address
that still slips through despite the extraction instruction.

**Why both, not just the prompt fix:** the prompt only shapes one of the two sources of
`location`. A picked calendar event's location is never passed through an LLM at all (design-
decisions.md §61 — a plain field copy), so a prompt-only fix would leave that path exactly as
fragile as it was found.

**Why both, not just the geocoding fallback:** the fallback still has to guess which segment is
the city by position (left-to-right, most-specific-first) — it has no semantic understanding of
what it dropped. The prompt fix gets the common case (a stated free-text location) right at the
source, with an actual understanding of what's a venue versus a place name, rather than relying
on comma-position heuristics for input the extraction could have gotten right the first time.

### Explicitly not built (product direction, not a resource cut)

- **Device/browser geolocation (lat/lon).** Considered and explicitly declined — the ask was
  "based on city and location of the event," not the user's live coordinates. `get_weather()`'s
  forecast call already accepts raw lat/lon (Open-Meteo's endpoint takes them directly — only
  the geocoding step needed a place name), so this remains a small, separable addition if wanted
  later, but nothing here builds toward it.
- **Weather forecasting for a future date/time.** `get_weather()` only ever resolves *current*
  conditions — there is no date parameter anywhere in this call. A styling request made today
  for an event tomorrow night reflects today's weather, not tomorrow's. Noted as a real,
  separate gap (found during the same investigation), not fixed here.
- **Calendar-location seeding beyond a brand-new thread** (§61's existing scope) — unchanged.

### Rejected alternatives

| Option | Rejected because |
|---|---|
| **(a) chosen** — prompt-level city preference + geocoding-level coarsening fallback, both additive | — |
| Geocoding fallback only, no prompt change | Leaves the extraction producing full addresses by default; works, but every free-text mention pays the cost of 2-4 wasted geocode calls before landing on the city, instead of getting there in one. |
| Prompt change only, no geocoding fallback | Leaves calendar-event locations exactly as fragile as found — no LLM sits in that path to apply the same instruction. |
| Parse/strip the address in Python (e.g. regex for the last comma-separated segment) instead of a request-level fallback | Indistinguishable from the fallback already built for the *common* case, but a single fixed position (e.g. "always the last segment") breaks for addresses that end in a plus code or postal code rather than a country; trying multiple positions in order, cheaply, against the real geocoder is what the fallback already does. |

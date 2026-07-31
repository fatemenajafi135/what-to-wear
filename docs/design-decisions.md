# Design decisions

Resolutions for everything `design/design-system.md` leaves incomplete, ambiguous, or
self-contradictory, plus the form-control specification it never contains.

**Status of this file:** `design/design-system.md` remains the source of visual truth. This
document is the second half of that contract — it only ever *fills gaps* or *resolves
contradictions* in it, never overrides a value it states clearly. Where the two disagree,
that disagreement is called out explicitly below with a decision and a reason.

Every value here is derived from tokens already defined in §1.1/§1.2. Nothing is invented.

Every item in this document is decided. Nothing is left open.

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

---

*All items in this document are decided. Nothing is left open.*

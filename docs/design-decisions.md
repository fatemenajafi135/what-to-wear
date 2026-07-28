# Design decisions

Resolutions for everything `design/design-system.md` leaves incomplete, ambiguous, or
self-contradictory, plus the form-control specification it never contains.

**Status of this file:** `design/design-system.md` remains the source of visual truth. This
document is the second half of that contract — it only ever *fills gaps* or *resolves
contradictions* in it, never overrides a value it states clearly. Where the two disagree,
that disagreement is called out explicitly below with a decision and a reason.

Every value here is derived from tokens already defined in §1.1/§1.2. Nothing is invented.

Items marked **NEEDS YOUR CALL** are product decisions left open.

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
Label            10.5px / 700, --color-text-secondary, sentence case
[ Control ]      44px min height
Help or error    10.5px / 400, --color-text-secondary or --color-error
```

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
| Font | `--font-size-base` (15px) / 22px line-height, weight 400 |
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

**Password fields** carry a show/hide toggle: an `IconButton` at `size=28` inset at the
trailing edge, Lucide `eye` / `eye-off`, `aria-label` "Show password" / "Hide password",
`aria-pressed` reflecting state. The 44px hit-area pseudo-element applies and may overlap
the input's padding box.

### 1.3 `Textarea`

Identical to `Input` except: `min-height: 88px` (two rows), `padding: 11px 12px`,
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

**NEEDS YOUR CALL:** the 8-character minimum is a placeholder. Supabase Auth's default is 6.
Confirm the real rule before feature 002.

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

## 6. The type scale and the token scale barely intersect

Tokens are 11/13/15/17/20/24/28px. Actual screen text is 26/16/13/12.5/10.5/10px. Only 13
and 20 overlap, so body copy, labels and captions have no token — which makes §1's *"every
component reads only these names"* false for typography.

**Decision:** tokenize the display scale rather than restyle the app, so the claim becomes
true with zero visual change:

```css
--font-size-2xs: 10px;    /* Caption */
--font-size-xs2: 10.5px;  /* Label, meta lines */
--font-size-sm2: 12.5px;  /* Body */
--font-size-md2: 16px;    /* Section title */
--font-size-3xl: 26px;    /* Display */
```

**NEEDS YOUR CALL, separately:** 12.5px body text and a stated 10px floor are small for a
real viewport. These values came from a mockup rendered inside a fixed phone bezel; at true
desktop width they will read tiny, and §8 already flags that contrast must be re-verified
*"once real type is set"*. I would raise body to 13px and the floor to 11px at 768px+ via a
single scale step, leaving mobile untouched. This is a visual change, so it is your call.

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

## 11. Still open

| # | Question | Why it needs you |
|---|---|---|
| 1 | Password minimum length (§1.7) | Supabase default is 6; I assumed 8 |
| 2 | Raise body text from 12.5px at 768px+ (§6) | A real visual change to the design |
| 3 | `wardrobeMinItems = 5` | Outfits are 3–4 pieces, so five items is barely one outfit. A product threshold, not a design value. |

Everything else above is decided and ready to implement.

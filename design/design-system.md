# What to Wear — Design System

Single-source implementation spec for the What to Wear app. Written for a coding agent with no access to the visual prototype — every value, state, and route is spelled out. This document is **LTR-only**; RTL is a deferred, separately-specified pass (see `known-gaps.md`).

Companion file: **`known-gaps.md`** — everything here that cannot be expressed in the prototyping tool (real focus-visible, PWA install/service-worker plumbing, focus trapping, RTL, etc.) plus a list of prototype-only scaffolding that must not ship.

### Brand mark
The logo (`logo.svg`, required asset — the implementer must have this file, it is not reproducible from a text description alone) is a rounded-square tile (`--color-surface` fill) containing a single-line line-art glyph: a wardrobe hanger hook, viewed as a coat-hanger silhouette with two sweeping garment-drape strokes fanning down-left and down-right from the hook, rendered in `--color-primary` at a heavy rounded stroke weight. Two small four-point sparkle/glint accents sit near the upper-right of the hook, solid-filled in `--color-primary`. Used at 240×240 source size; scales down to as small as 32px (boot screen) without simplification. Per `known-gaps.md` §0.5, the sparkle-accent position is fixed and does not mirror under RTL.

---

## 1. Design tokens

Three layers, in order of how rarely they change:

1. **System tokens** — spacing, radius, shadow recipe, motion, z-index, the UI font-size scale. Identical in light and dark; these are structural, not thematic.
2. **Semantic color tokens** — `--color-*` names that describe *purpose* (primary, surface, text-secondary, error), not a literal hue. Every component and screen reads only these names, never a hex value. This is the layer that flips between light and dark.
3. **Theme blocks** — the two concrete value sets (`light`, `dark`) that populate the semantic layer. Adding a theme (e.g. a high-contrast mode) means adding a third block that assigns the same semantic names; nothing downstream changes.

Font: **Instrument Sans** (weights 400/500/600/700), loaded from Google Fonts, with a system fallback stack: `'Instrument Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`.

### 1.1 System tokens (theme-independent)

```css
:root {
  /* motion */
  --motion-duration-fast: 120ms;
  --motion-duration-base: 200ms;
  --motion-duration-slow: 320ms;
  --motion-easing-standard: cubic-bezier(0.4, 0, 0.2, 1);
  --motion-easing-decelerate: cubic-bezier(0, 0, 0.2, 1);
  --motion-easing-accelerate: cubic-bezier(0.4, 0, 1, 1);

  /* z-index scale */
  --z-sticky: 10;
  --z-dropdown: 20;
  --z-overlay: 30;
  --z-modal: 40;
  --z-toast: 50;
  --z-tooltip: 60;

  /* UI font-size scale (component text; see §2 for the separate heading/display scale) */
  --font-size-xs: 11px;
  --font-size-sm: 13px;
  --font-size-base: 15px;
  --font-size-md: 17px;
  --font-size-lg: 20px;
  --font-size-xl: 24px;
  --font-size-2xl: 28px;

  /* radius */
  --radius-sm: 8px;      /* controls: buttons, inputs, chips-square */
  --radius-md: 14px;     /* cards */
  --radius-lg: 20px;     /* sheets/modals */
  --radius-pill: 999px;  /* chips, pills, switch track */
  --radius-circle: 50%;  /* avatars, icon buttons, FAB */

  /* spacing */
  --space-xs: 4px;   /* tight icon gaps */
  --space-sm: 8px;   /* chip/icon gaps */
  --space-md: 12px;  /* card internal gaps */
  --space-lg: 16px;  /* card padding */
  --space-xl: 24px;
  --space-2xl: 32px;
  --space-3xl: 40px;
  --space-4xl: 48px;
  --space-5xl: 56px;

  --focus-ring-offset: 2px;
}
```

### 1.2 Semantic tokens + theme blocks

```css
:root, [data-theme="light"] {
  --color-primary: #4B2E52;
  --color-primary-hover: #3A2440;
  --color-on-primary: #FFFFFF;

  --color-text-primary: #241F2B;
  --color-text-secondary: #69626E;

  --color-background: #E6E1D6;             /* app shell / screen background */
  --color-surface: #F8F6F1;                /* cards, sheets, raised rows */
  --color-surface-sunken: #EFEADD;         /* wells: skeletons, chip-inactive fill, input backgrounds */
  --color-border: #D9D2C4;
  --color-accent-soft: #E7DEE6;            /* secondary-button fill, citation badge fill */
  --color-on-accent-soft: #241F2B;
  --color-overlay: rgba(36, 31, 43, 0.45); /* modal/sheet scrim */

  --color-error: #B3261E;
  --color-success: #386F4A;
  --color-warning: #88590E;
  --color-focus-ring: #4B2E52;

  --shadow-color-neutral: rgba(0, 0, 0, 0.06);
  --shadow-color-tint: rgba(75, 46, 82, 0.35);
  --shadow-color-elevation: rgba(36, 31, 43, 0.18);
  --shadow-xs: 0 1px 3px var(--shadow-color-neutral);
  --shadow-sm: 0 4px 10px var(--shadow-color-tint);      /* FAB / primary CTA */
  --shadow-md: 0 8px 20px var(--shadow-color-elevation); /* menus / sheets */
  --shadow-focus-ring: 0 0 0 var(--focus-ring-offset) var(--color-focus-ring);
}

[data-theme="dark"] {
  --color-primary: #C9A6D6;
  --color-primary-hover: #D9BEE2;
  --color-on-primary: #241F2B;

  --color-text-primary: #F2EFEA;
  --color-text-secondary: #908996;

  --color-background: #1C1822;
  --color-surface: #262130;
  --color-surface-sunken: #201C28;
  --color-border: #3A3440;
  --color-accent-soft: #3A3044;
  --color-on-accent-soft: #F2EFEA;
  --color-overlay: rgba(0, 0, 0, 0.55);

  --color-error: #E8998F;
  --color-success: #8FCB9C;
  --color-warning: #E3B166;
  --color-focus-ring: #C9A6D6;

  --shadow-color-neutral: rgba(0, 0, 0, 0.3);
  --shadow-color-tint: rgba(0, 0, 0, 0.5);
  --shadow-color-elevation: rgba(0, 0, 0, 0.5);
  /* --shadow-xs/sm/md and --shadow-focus-ring formulas are unchanged — they reference the color vars above */
}
```

`data-theme` is set on the document root. **Boot-time theme selection is a real gap** (the prototype always boots `light`) — see `known-gaps.md`; implement by reading `prefers-color-scheme` before first paint, falling back to a persisted user override.

---

## 2. Type scale

Two tiers. The **UI scale** (`--font-size-*`, §1.1) is what every component reads. The **display/heading scale** below is literal one-off sizing used directly on screens for hero copy and headings — it is not tokenized in the prototype, and the line-heights are this document's recommended pairings (the prototype relies on default line-height for most of these; ship the paired values below instead).

| Style | Size / weight | Line-height | Used for |
|---|---|---|---|
| Display | 26px / 700 | 32px (1.23) | Recommend hero title ("I need a few more pieces…"), boot/splash wordmark |
| Screen Title (`<h1>`) | 20px / 700 | 25px (1.25) — matches `--font-size-lg` | TopHeader titles: Closet, Outfits, Profile, Settings, Item details, etc. |
| Section Title (`<h2>`) | 16px / 700 | 21px (1.3) | Sub-page headers: Profile's three card headings, sheet titles |
| Card Title | 13px / 700 | 18px (1.4) — matches `--font-size-sm` | Outfit card titles, list-row titles |
| Body | 12.5px / 400 | 19px (1.55) | Chat bubbles, item/outfit descriptions, empty/error copy |
| Label | 10.5px / 700, `--color-text-secondary` | 14px (1.3) | Field labels, eyebrow text |
| Caption | 10px / 600, `--color-disabled`/faint | 14px (1.4) | Timestamps, meta text |

UI scale pairings (component text):

| Token | Size | Recommended line-height |
|---|---|---|
| `--font-size-xs` | 11px | 14px (1.27) |
| `--font-size-sm` | 13px | 18px (1.38) |
| `--font-size-base` | 15px | 22px (1.47) |
| `--font-size-md` | 17px | 23px (1.35) |
| `--font-size-lg` | 20px | 25px (1.25) |
| `--font-size-xl` | 24px | 30px (1.25) |
| `--font-size-2xl` | 28px | 34px (1.2) |

Minimum body text anywhere in the product is 10px (caption); never go smaller.

---

## 3. Component inventory

Every component reads only semantic tokens (§1.2). "Hover" applies only under `@media (hover: hover)` (pointer devices) — never simulate hover on touch.

### The 44px hit-area pattern (apply everywhere a visual control is smaller than 44×44px)

Any icon-only button, chip, switch, tab, or non-full-width text button whose visible box is under 44px in either dimension gets an invisible centered pseudo-element that expands the *tap target* without growing the *paint*:

```css
.control { position: relative; }
.control::after {
  content: '';
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  min-width: 44px;
  min-height: 44px;
}
```

This satisfies WCAG 2.5.5/2.5.8 and iOS/Android HIG minimums. Skip it only on controls that are already naturally ≥44px in both dimensions (full-width `Button`, BottomSheet rows at ~48px tall). It is applied today on: Button (intrinsic-width variants), IconButton, Chip, Switch, SegmentedControl options, TabBar items, TopHeader's right pill, BottomSheet rows, Banner's action link.

⚠ Today this pattern pairs with a bare `:focus` ring rather than `:focus-visible` — fix per `known-gaps.md` §1 before shipping (the ring must not appear on mouse/touch activation).

### Button
Variants: `primary` / `secondary` / `outline`. Width modes: `fullWidth` (default, spans container) / intrinsic (`fullWidth=false`) / `stretch` (forces 100% width even where intrinsic would otherwise apply — used for form buttons, see §5).

| State | Primary | Secondary | Outline |
|---|---|---|---|
| Default | `--color-primary` bg, `--color-on-primary` text | `--color-accent-soft` bg, `--color-on-accent-soft` text | transparent bg, `--color-primary` border+text |
| Hover (pointer) | `--color-primary-hover` bg | `--color-border` bg | `--color-surface-sunken` bg |
| Active/pressed | `--color-primary-hover` bg | `--color-border` bg | `--color-surface-sunken` bg |
| Focus-visible | + `--shadow-focus-ring` | same | same |
| Disabled | opacity 0.5, `disabled` attr (no pointer events) | same | same |

**Disabled convention (all components):** disabled is always `opacity: 0.5` + `pointer-events: none` (or a `disabled` attr) applied to the control's normal colors — never a dedicated "disabled" color token. Button, Switch, SegmentedControl, IconButton, and Chip all follow this one rule.
| Loading | button replaced by a skeleton-pulse block at the same footprint; not clickable | — | — |
| Error | dedicated error treatment: transparent bg, `--color-error` border+text, shows `errorLabel` (default "Try again") in place of the normal label | — | — |

Full-width buttons are ≥44px tall from padding alone (12px top/bottom + text). Intrinsic buttons use the 44px pseudo-element pattern regardless of their 11px×18px padding box.

### IconButton
Icon library: **Lucide** (`lucide-react` or the static SVG set) — matches the current 2–2.2px rounded stroke weight used throughout the prototype's inline icon markup. Exact Lucide names per keyword:

| Keyword | Lucide icon |
|---|---|
| `back` | `arrow-left` |
| `close` | `x` |
| `settings` | `settings` |
| `dots` | `ellipsis` |
| `heart` | `heart` |
| `heartFilled` | `heart` with `fill="currentColor"` |
| `filter` | `sliders-horizontal` |
| `calendar` | `calendar` |
| `history` | `history` |
| `plus` | `plus` |
| `thumbsUp` | `thumbs-up` |
| `thumbsDown` | `thumbs-down` (the `thumbs-up` glyph rotated 180° around its own center — not a separate path — so the two stay visually paired) |

Visual size 28–48px (default 34), circular, `--color-surface-sunken` bg with `--color-border` outline, `--color-primary` glyph.
States: default → hover (`--color-border` bg) → active (same) → focus-visible (ring) → disabled (opacity 0.5, `disabled` attr).
`aria-label` defaults per icon (Back, Close, Settings, More options, Save/Unsave outfit, Filter, Calendar, Chat history, Add), overridable via a `label` prop.
Hit area: 44×44 pseudo-element regardless of the `size` prop.

### Chip
Selectable pill (category/filter/style/color). States: `active` (dark `--color-primary` fill) / `inactive` (`--color-surface-sunken` fill), each with hover/active/focus-visible; a separate `disabled` state renders non-interactive (`pointer-events: none`, `opacity: 0.5`, no hover/active/focus) — the same opacity-dimming convention used by Button/Switch/SegmentedControl/IconButton, not a dedicated color token. No loading/error state.

### Badge
Non-interactive status pill. Tones: `citation` (small numbered pill, e.g. "1", "2" — a footnote-style reference to a styling rule, used **only in Outfit detail's description**, never in the chat outfit card — the chat card's description is plain text with no citation markers, since detail is where the full cited reasoning lives), `status` (accent-soft, e.g. "Connected"), `muted` (surface-sunken, e.g. "Coming soon"), `count` (solid circular numeral). **Never tappable** — it is not a link to the closet item; no states beyond tone.

**Closet-item thumbnails are the tappable element, not the citation Badge.** Assistant chat replies, Outfits gallery cards, and Outfit detail all render a separate row of small square garment-swatch thumbnails, unified at **56×56px** across every context — tapping one of *these* navigates to that item's Item detail screen (`/closet/:itemId`). The citation Badge and the item-thumbnail row are visually and functionally distinct: citations footnote a styling rule, thumbnails deep-link to the item.

### Scores
Each outfit carries a match score (0–1 float) used to compute the label shown in the chat pager card's header pill, the Outfits gallery card's header pill, and Outfit detail's "Match breakdown" section. Thresholds:
- **≥ 0.8 → "Great match"**
- **0.6–0.79 → "Good match"**
- **0.4–0.59 → "Might work"**
- **< 0.4 → not surfaced at all.** No label, pill, or bar renders for a score this low — the outfit is filtered out before it reaches any of these three surfaces rather than displayed with a discouraging label.

**No numeric score or percentage is ever displayed anywhere in the UI.** Every surface — the header pill on the chat/gallery card and the per-dimension bars in Outfit detail's Match breakdown — shows a label and/or a bar fill only; the underlying float and any percentage derived from it are never rendered as text.

### Switch
`role="switch"`, `aria-checked`, `aria-disabled`, keyboard-operable (Space/Enter), `tabIndex` 0 or −1 when disabled. Track: `--color-primary` (on) / `--color-border` (off). Thumb slides via `inset-inline-end`/`inset-inline-start` (logical — already RTL-safe). States: checked/unchecked × enabled/disabled, with hover/active/focus-visible on enabled. Hit area: 44×44 pseudo despite a 42×24 visual track. Thumb-slide transition needs reduced-motion gating — see `known-gaps.md`.

### SegmentedControl
2–3 option tab switcher. Each option: active (`--color-surface` fill, `--color-text-primary`) / inactive (transparent, `--color-text-secondary`), hover/active/focus-visible per option; a control-level `disabled` prop dims all options to opacity 0.5.

### TopHeader
Screen header: optional back `IconButton`, `<h1>` title + optional subtitle (both truncate with ellipsis), optional right slot (`none` / `icon` / `pill`). No states of its own beyond its children's.

### TabBar
Primary navigation, `role="navigation" aria-label="Primary"`. Three markups (bar/rail/sidebar) live as CSS-toggled siblings — see §5 for the breakpoint mechanism. Item states: active (filled icon + `--color-primary` text, `aria-current="page"`) / inactive (`--color-text-secondary`), with hover/active/focus-visible. The Create action is a non-route circular FAB on mobile, relocates per tier (§5). The Profile item swaps its generic icon for the user's `AvatarInitial` in the sidebar tier only.

### BottomSheet
Modal action sheet, bottom-anchored on mobile, becomes a centered dialog (all four corners rounded, max-width 420px) at tablet+ (§5). States: `loading` (3 skeleton lines), `error` (message + optional retry button), `empty` (`emptyLabel` text, default "Nothing here yet"), and normal (grouped rows). Row states: `default`/`danger` tone × enabled/disabled, with hover/active/focus-visible on enabled rows. Bottom padding respects safe area: `max(30px, env(safe-area-inset-bottom))`.
**Gap:** not yet real dialog semantics — needs `role="dialog" aria-modal="true" aria-labelledby="<title id>"` plus focus trap/restore (§7 and `known-gaps.md`).
**Bespoke variants not on this component** (by design — see readme.md): the "Add to Closet" sheet (icon+title+description rows) and the Outfits "Filter & sort" sheet (mixed sort-chip/filter-chip layout) are custom markup in the app shell, richer than BottomSheet's plain label rows.

### Outfit suggestion pager (Recommend assistant bubble)
When one assistant reply carries multiple outfit suggestions (a variable count, 1–4+ in practice), it renders as a horizontal pager of outfit cards inside that assistant bubble, instead of the single flat item-thumbnail row used for a one-outfit reply. **The card is its own variant, distinct from the Outfits-gallery card.** Each card, top to bottom:
1. Header row: outfit title (13px/700, truncates) with the overall match label immediately to its right as a small pill (`--color-accent-soft` fill, `--color-primary` text, `radius-pill`, 10.5px/700 — see § Scores) — then a flexible spacer, then a dedicated favorite toggle (outline/filled heart, same glyph pair as the Outfits gallery's heart) at the far right of the row. Tapping the heart calls the same favorite state the gallery card's heart displays, so a saved suggestion shows up favorited in Outfits too — this is the pattern's **only** path to favoriting a suggestion, independent of the feedback controls in the footer.
2. Description: the styling explanation as **plain text directly on the card** — no nested tinted surface, no inline citation `Badge`s. (Citations are detail-page-only, see § Badge.) The description is the plain sentence with no trailing artifact — earlier revisions carried an orphan citation-closing period; that's gone along with the citations themselves.
3. The unified item-thumbnail grid, wrapping onto additional rows (unchanged — see **Item count & overflow** below).
4. Meta line (10.5px secondary, `{occasion} · {formality|weather}`) — sits below the thumbnail grid, not under the title.
5. Footer row: thumbs-down then thumbs-up, right-aligned. **Pure feedback on the suggestion — not a save/favorite action.** Mutually exclusive per card, each toggles off on a second tap; no persisted effect on the outfit itself (a future build should send this as a signal to the recommender). Same 34px visual / 44px hit-area IconButton treatment; thumbs-up fills solid `--color-primary`/`--color-on-primary`, thumbs-down fills solid `--color-text-secondary`/`--color-surface`, when pressed.

**Item count & overflow.** An outfit can carry as few as **1** item up to a realistic ceiling of about **10** (typically 3–4 pieces) — the layout must hold at either end without ever hiding an item behind a fixed truncation that loses information. The three surfaces that render an item row handle overflow differently, deliberately:
- **Chat outfit card (pager, above, and any single-outfit chat reply):** thumbnails sit in a **CSS grid that wraps onto additional rows** — never scroll horizontally — because the card already sits inside a horizontally-swiping pager (or, for a single-outfit reply, establishes the same visual pattern). Nested same-axis scrolling would make a swipe gesture ambiguous (paging outfits vs. scrolling thumbnails). Card height grows to fit the wrapped rows; the pager/swipe gesture keeps sole ownership of the horizontal axis. Grid columns (56px thumbnails, 6px gap): **4 columns at mobile** (matching the chat column's narrower 90%-max-width bubble cap — never wider than an assistant message can be), **8 columns at tablet/desktop** (the pager card widens to ~92% of its wider track there).
- **Outfits gallery card:** shows up to **4** real thumbnails when the outfit has 4 or fewer (no phantom empty slots). Past 4, it shows only the first **3** real thumbnails, then a **"+N" overflow chip** (surface-sunken fill, bordered, same 52px size) in the 4th slot (N = total − 3) — tapping the chip opens Outfit detail like the rest of the card. The row never exceeds 4 slots either way, so every card in the list stays the same width and height regardless of item count.
- **Outfit detail:** a **CSS grid showing every item** — no scrolling, no cap, no chip; the page itself scrolls vertically to reveal additional rows same as any other content. Unlike the other two surfaces, tiles here are **deliberately large** (fraction-based columns, not fixed 56px) since this is the one screen dedicated to examining the garments themselves: **2 columns at mobile**, **3 at tablet/desktop** — see § Image treatment for exact sizing.

The card itself (outside the header favorite button, the thumbnails, and the footer) is tappable → navigates to that suggestion's Outfit detail — where the full citation-backed reasoning (numbered `Badge`s inline in the description + the rule list explaining each one) lives, per § Badge.

**Pager mechanics:**
- **At mobile widths, the track shows exactly one card with no native scroll/swipe at all** (`overflow:hidden`; a CSS `transform: translateX(-100%×index)` slide, animated, is the only way the visible card changes) — paging is arrow-button-only on mobile, precisely so there's a single unambiguous way to move between suggestions on a touch screen. **At tablet/desktop widths the track becomes a native horizontal scroller** (`scroll-snap-type: x mandatory`, one card per snap point via `scroll-snap-align: center`, swipeable/draggable, hidden scrollbar) with each card narrowed to ~92% width so neighboring cards peek at both edges — pointer/trackpad users get a scrollable hint of more content, and the same arrow row still works identically at both breakpoints.
- **Prev/next controls are real `<button>`s**, not swipe-only affordances, placed **below the card track as their own control row together with the position indicator** — not overlaid on the card, so they read as paging the group of suggestions rather than scrolling the item thumbnails inside one outfit. Each is a 32px visual circle (`--color-surface` fill, bordered, `--shadow-xs`) with the standard 44px hit-area pseudo-element, a descriptive `aria-label` ("Previous suggestion" / "Next suggestion"), and native `disabled` at the first/last card (`opacity 0.35`, genuinely inert and skipped in tab order) — reachable and operable by keyboard/AT without relying on the scroll container. Advancing scrolls the track programmatically (`scrollTo` by card width) and keeps the visible card in sync with swipe position via a `scroll` listener.
- **Both controls are hidden outright — not just disabled — when the group has exactly one card.**
- **Position indicator** ("2 of 4") sits directly between the two arrow buttons in that same control row — never detached elsewhere in the bubble — and only appears alongside them (count > 1).
**Group-level states** (the assistant bubble shows exactly one of these at a time, replacing the old single-item response for this message):
- **Loading**: a single skeleton card (pulse blocks for title/meta, a description-shaped bar, and a row of three 56×56 thumbnail placeholders — no arrows/indicator since the count isn't known yet) appears in place of the pager immediately when the user takes the styling action — this is the group's own loading treatment, not a shared trailing "Styling your outfit…" caption.
- **Ready**: the pager as described above.
- **Empty** (the request produced zero viable outfits): no pager; a single message-shaped card with `"I couldn't put an outfit together from that — try loosening a constraint or adding a few more pieces."`, the trailing phrase linking to Add item — follows the standard empty-state copy convention (explain + one recovery action).
- **Error** (the generation request failed): no pager; a card with `"Something went wrong pulling outfit options together."` + a `--color-error`-styled "Try again" button (Button's Error treatment, § Button) that re-runs the same request in place.

### AvatarInitial
Display-only circular initial avatar, size 32–72px, `--color-primary` fill, single uppercase initial. No interactive states.

### Banner
Full-width inline strip. Variants: `offline` / `error` (both `--color-surface-sunken` bg) / `info` (`--color-accent-soft` bg). Optional trailing action (underlined text button, hover=opacity 0.7, focus ring, 44px hit area) or no action (plain text). `role="status" aria-live="polite"` still needs to be applied — see §7.

---

## 4. Screen graph

14 screens across two stacks. **Routes and destinations are identical across mobile/tablet/desktop** — only chrome (bottom bar vs. rail vs. sidebar) and pane arrangement change (§5).

### Auth stack (signed out)
| Route | Screen | Notes |
|---|---|---|
| `/signin` | Sign in | Default when signed out |
| `/signup` | Sign up | |
| `/forgot-password` | Forgot password | Confirmation state, no separate route |
| `/reset-password/:token` | Reset password | Landed on from the link in the reset email. States: **form** (token valid — new password + confirm-password fields, `stretch` submit button per §5); **error** (token invalid/expired — `auth.reset.error.body`: "This link has expired. Request a new one." + `auth.reset.error.cta`: "Resend link", returns to `/forgot-password`); **success** (`auth.reset.success.body`: "Your password has been updated." + `auth.reset.success.cta`: "Sign in", returns to `/signin`). Not reachable from in-app navigation — only from the emailed link. |

### Authenticated app (persistent nav chrome)
| Route | Screen | Reached from |
|---|---|---|
| `/recommend` | Styling (Recommend) | Default on sign-in; primary nav |
| `/history` | Chat history | Recommend header's history icon |
| `/history/:sessionId` | Session detail | Tapping a row in Chat history; "Continue" resumes into `/recommend` with that session's context |
| `/calendar` | Calendar events | A "style for an event" suggestion chip on Recommend |
| `/closet` | Closet (grid) | Primary nav |
| `/closet/:itemId` | Item detail | Tapping a closet item; overflow (⋯) opens the item-menu BottomSheet (Edit / Log as worn today / Favorite / Delete) |
| `/add` | Add item | The Create FAB/pill (not a persisted destination — an overlay flow: upload photo → review queue, with a bulk-upload branch); closing returns to the screen underneath |
| `/outfits` | Outfits (gallery) | Primary nav |
| `/outfits/:outfitId` | Outfit detail | Tapping an outfit card; overflow opens the outfit-menu BottomSheet |
| `/profile` | Profile | Primary nav |
| `/profile/settings` | Settings | Profile's gear icon; back arrow returns to `/profile`. In-page section switcher (not sub-routes): Style preferences, Body & size, Account, Connected accounts, Notifications |

The Create action is deliberately **not** a 5th nav destination — it's an overlay launcher, positioned differently per tier (§5).

### Settings section contents
Settings' five sections (in-page switcher, not sub-routes) and their real fields:

| Section | Fields / controls |
|---|---|
| **Style preferences** | Style tags (multi-select chips): Classic, Minimal, Bold, Casual, Edgy. Color preference tags (multi-select chips): Neutral tones, Jewel tones, Pastels, Monochrome, Earth tones. "Brands to avoid" — free-text tag input (type + Enter to add a chip, × to remove). |
| **Body & size** | Body shape (single-select, 5 illustrated options): Hourglass, Pear, Rectangle, Apple, Inverted triangle. Gender (single-select chips): Woman, Man, Non-binary, Prefer not to say. Birth date (date picker). Sizes: Height (text/select, e.g. "5 ft 6 in"), Top size (select: XXS–XXXL), Bottom size (select: 00–20), Shoe size (select). |
| **Account** | Email address (editable text field). No password-change, delete-account, or data-export controls exist yet — deferred, see `known-gaps.md` §0.6. |
| **Connected accounts** | Google Calendar: connect/disconnect toggle (shows a "Connected" status Badge when linked, a "Connect" text action when not). Weather services: listed with a "Coming soon" muted Badge, not yet interactive. |
| **Notifications** | Push notifications: single on/off `Switch`, default **on**. |

Each section (except Notifications, which has no edit/done state) has an Edit/Done toggle: tapping "Edit" reveals the editable controls above; tapping "Done" commits the draft back to the saved value.

---

## 5. Responsive rules

### Breakpoints (CSS-only — no JS media query, no flash on first paint)

| Tier | Width | Nav chrome |
|---|---|---|
| Mobile | 0–767px | Bottom tab bar |
| Tablet | 768–1023px | Left icon rail, 76px, icon-only |
| Desktop | 1024px+ | Left sidebar, 240px, icon + label |

Implement with a real viewport media query (`@media (min-width: …)`) or a container query on the top-level app-shell element in a real responsive/PWA build. (The prototype demos this via a container query scoped to a fixed device-bezel wrapper, purely because it's rendered inside a device frame for presentation — that mechanism does not carry over; use the app's actual shell.)

### Nav mapping per tier (destinations identical, per §4)

| Destination | Mobile (bar) | Tablet (rail) | Desktop (sidebar) |
|---|---|---|---|
| Recommend | Icon+label | Icon only | Icon+label |
| Closet | Icon+label | Icon only | Icon+label |
| **Create** (opens `/add`, not a route) | Floating circular FAB, centered, elevated −18px, between Closet/Outfits | Circular "+" icon button pinned to the top of the rail, above a divider | Full-width labelled pill "+ New item", primary color, pinned below the wordmark, above the divider |
| Outfits | Icon+label | Icon only | Icon+label |
| Profile | Icon+label (generic icon) | Icon only | Icon+label; swaps to the user's `AvatarInitial`, pinned to the bottom with a top divider |

Active state: filled icon + `--color-primary` text on all tiers; the sidebar additionally gets a 3px accent bar on the item's inline-start edge (logical — auto-relocates under RTL). `aria-current="page"` on the active item on all three.

### Two-pane master-detail (desktop, 1024px+, only)

At desktop, list+detail screen pairs become simultaneous side-by-side panes instead of push navigation:

- **Narrow list** (320px fixed): Settings' section list beside its section detail.
- **Wide list** (flexible, ~1.6fr): Closet grid, Outfits gallery, Chat history list — each beside its detail pane.
- **Detail pane**: flexible, capped at 680px, centered within its own space.

At **tablet** (768–1023px), these same pairs stay as separate, pushed screens (no side-by-side list) — the tablet reflow instead applies to *within* a single detail screen (e.g. Item detail: photo fixed 40% width on the left, details on the right — a two-column layout on one screen, not a list/detail pair).

### Content width caps

At 1024px+, a screen's scrollable content column is capped and centered (`max-width; margin-inline: auto`) rather than stretching edge-to-edge — except the two grid galleries (Closet, Outfits), which use the extra width for more columns instead. Recommend's chat column specifically caps at 480px on tablet / 560px on desktop (its own reflow, tighter than the general cap, to keep chat line length readable). Calendar events and Chat history cap at 640px on both tiers (plain lists, no grid).

| Screen | Mobile | Tablet | Desktop |
|---|---|---|---|
| Sign in / Sign up / Forgot password | Full-bleed, max-width 360px | Same, centered | Same; gains a `--color-surface` panel, max-width 400px |
| Recommend | Single column | Caps at 480px | Caps at 560px |
| Closet | 2-col grid | 3-col grid | 4-col grid |
| Item detail | Stacked: photo full-width, details below | Two-column: photo 40% left, details right | Same as tablet |
| Add item | Stacked, one-at-a-time review card | Same, centered, max-width 480px | Same |
| Outfits gallery | 2-col grid | 3-col grid | 4-col grid |
| Outfit detail | Stacked | Two-column: image/collage left, meta+actions right | Same as tablet |
| Calendar events / Chat history | List | Same, max-width 640px | Same |
| Session detail | Chat column | Same reflow as Recommend | Same |
| Profile / Settings | Stacked, full width | 2-col grid (3rd card wraps) | All 3 cards in a row, ~340px each |
| Overlays (item menu, outfit menu, filter sheet, add sheet) | Bottom sheet, full width | Centered modal dialog, max-width 420px, all corners rounded | Same as tablet |

### Button width rule

- **Form buttons** (inside a form context — auth screens, item-edit form, add-item forms) always render at **100% width, matching the width of their sibling input fields**, at every breakpoint. This is the `stretch` mode on Button.
- **Content buttons** (empty-state CTAs, retry buttons, any button not attached to a form) are full-width on mobile (thumb-friendly), but become **intrinsic width with `min-width: 140px`, left/start-aligned**, once the viewport reaches 768px+ — a full-bleed button looks wrong once the column is wider than a phone screen. Secondary/outline content buttons use `min-width: 100px` instead of 140px (they're visually lighter and don't need the same minimum).

### Filter & sort dimensions

**Closet** — filter only (single-select chip row, no sort): All, Tops, Bottoms, Outerwear, Shoes, Accessories.

**Outfits** — opens a "Filter & sort" BottomSheet with three independent single-select filter facets (each defaulting to "All") plus one sort:
- Occasion: All, Dinner, Commute, Work, Everyday
- Weather: All, Rainy, Mild, Warm, Cold
- Formality: All, Casual, Business casual, Formal
- Sort by (single-select, one active at a time): Date added (default), Favorited first, Most worn

A numeric badge on the filter icon shows the count of non-"All" facets active; a "Clear" link resets all three facets to "All" (sort is unaffected by Clear).

---

## 6. All screen states

Every screen supports `loading` (skeleton), `error` (message + retry), and `offline` (global banner, per-action disabling — see below). Screens with collections also support `empty` (no data at all) and, where filtering exists, `empty-filtered` (data exists, current filter matches nothing) as a **distinct** state from empty — the copy and the recovery action differ (clear filter vs. go create something).

**Error vs. offline — explicit rule:** `error` means a request reached the server and failed (4xx/5xx, or a server-side processing failure); `offline` means the client has no network at all (`navigator.onLine` false). They are not mutually exclusive UI states — offline is a **global, persistent** condition (sticky banner + dimmed/disabled actions) that can be visible at the same time as any screen underneath it. **Offline wins for messaging**: while offline, a screen must not additionally show its own `error` copy for a failure that is simply the absence of network (that would double-message the same root cause) — suppress the screen-level error state and rely on the offline banner alone. Once reconnected, if a request still fails for a real server-side reason, the screen's own `error` state takes over normally.

i18n keys below use dot namespacing: `screen.state.role`. Copy is the real prototype microcopy — ship it verbatim pending localization.

### Auth
| Key | Copy |
|---|---|
| `auth.signin.error.body` | That email and password don't match. Try again or reset your password. |
| `auth.signup.error.body` | We couldn't complete your sign-up with those details. Check them and try again, or sign in below. |
| `auth.forgot.error.body` | Something went wrong sending that email. Try again in a moment. |
| `auth.forgot.sent.body` | Check your inbox: if an account exists for **{email}**, a reset link is on its way. |
| `auth.forgot.sent.cta` | Back to sign in |

### Recommend
| Key | Copy |
|---|---|
| `recommend.insufficient_closet.body` | I need a few more pieces to work with — add at least {wardrobeMinItems} items so I can put outfits together. |
| `recommend.insufficient_closet.cta` | Add items to your closet |
| `recommend.error.body` | Something went wrong pulling that together. |
| `recommend.error.cta` | Try again |

(`wardrobeMinItems` = 5 in the prototype; treat as a real config value, not hardcoded copy.)

### Closet
| Key | Copy |
|---|---|
| `closet.empty.first_run.body` | Your closet is empty. Add a few pieces and I'll start suggesting outfits. |
| `closet.empty.first_run.cta` | Add your first item |
| `closet.empty.filtered.body` | No items match this filter. |
| `closet.empty.filtered.cta` | Clear filter |
| `closet.error.body` | Couldn't load your closet. |
| `closet.error.cta` | Retry |

### Item detail
| Key | Copy |
|---|---|
| `item_detail.error.body` | This item couldn't be found — it may have been removed. |
| `item_detail.error.cta` | Back to Closet |

### Add item
**Review card fields** (one card per queued photo, Save & next / Save to Closet to advance): Name (text, scan-auto-filled, editable), Category (single-select chips: Tops/Bottoms/Outerwear/Shoes/Accessories, scan-auto-filled, editable), Group (text, e.g. "Blazers", scan-auto-filled, editable), Fabric (text, scan-auto-filled, editable), Color (text, scan-auto-filled, editable), Notes (text, scan-auto-filled, editable). Every field is scan-auto-filled as a starting value and every field is manually editable — none are read-only or manual-entry-only.

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
| `add_item.review.position` | Reviewing item {position} (promote to a live-announcing `<h2>`, see §7) |

### Outfits
| Key | Copy |
|---|---|
| `outfits.empty.first_run.body` | No outfits yet. Ask me to style something and I'll save the looks here. |
| `outfits.empty.first_run.cta` | Go to Styling |
| `outfits.empty.filtered.body` | No outfits match these filters. |
| `outfits.empty.filtered.cta` | Clear filter |
| `outfits.error.body` | Couldn't load your outfits. |
| `outfits.error.cta` | Retry |

### Calendar
| Key | Copy |
|---|---|
| `calendar.disconnected.title` | Connect your calendar |
| `calendar.disconnected.body` | Link Google Calendar so I can suggest outfits for what is actually on your schedule. |
| `calendar.disconnected.cta` | Connect Google Calendar |
| `calendar.empty.body` | Nothing on your calendar this week. Ask me to style for any plan instead. |
| `calendar.empty.cta` | Style something |
| `calendar.error.body` | Couldn't sync your calendar. |
| `calendar.error.cta` | Retry |
| `calendar.list.hint` | Pick an upcoming event to style for. |

### Chat history
| Key | Copy |
|---|---|
| `chat_history.empty.body` | No past conversations yet. Start styling and I'll save them here. |
| `chat_history.error.body` | Couldn't load your history. |
| `chat_history.error.cta` | Retry |

### Profile / Settings
| Key | Copy |
|---|---|
| `profile.error.body` / `settings.error.body` | That didn't save. Check your connection and try again. |
| `profile.error.cta` / `settings.error.cta` | Retry |

### Offline (global)
| Key | Copy |
|---|---|
| `offline.banner.body` | You're offline. Some actions are unavailable until you're reconnected. |

Offline behavior today is **display-only**: the banner shows and specific actions (upload, submit, "Log as worn", chat send) disable via `navigator.onLine`, but nothing is queued for retry — no promise of "we'll upload once you're back" is made in copy, because no such mechanism exists yet. See `known-gaps.md` if that promise is wanted.

---

## 7. PWA surfaces

None of this exists as working code in the prototype (no `manifest.json`, no service worker, no real camera/calendar calls) — full implementation spec lives in `known-gaps.md` §-2. Summary of what a real build needs:

- **`manifest.json`** — name/short_name "What to Wear", `display: standalone`, `orientation: portrait`, `background_color: #E6E1D6` (light approximation), `theme_color: #4B2E52`, icons at 192/512/512-maskable, two shortcuts (Add an item, Get a recommendation). Full JSON in `known-gaps.md`.
- **Per-mode status bar color** — both light/dark `<meta name="theme-color" media="(prefers-color-scheme: …)">` tags in `<head>` (the manifest field alone can't respond live), using `--color-background` per mode (the color actually adjacent to the status bar — every sticky header sits on background, not primary).
- **Install prompt (Android/Chrome)** — gate strictly on `beforeinstallprompt` having fired; if it never fires, the card must not render regardless of any engagement trigger.
- **iOS/Safari manual "Add to Home Screen" card** — must cover Safari, Chrome, Firefox, Edge, DuckDuckGo on iOS individually (each has a different Share entry point); gate on iOS platform detection and suppress when already `standalone`.
- **Update toast** — anchored `bottom: calc(90px + env(safe-area-inset-bottom))`, `z-index: var(--z-toast)`.
- **Permission priming** — camera (Add Item upload) and calendar (Google Calendar connect) both need a primer card before the real OS/OAuth prompt, each gated behind persisted "already primed" flags.
- **Safe-area rules** — `viewport-fit=cover` is already set; every fixed/sticky offset at a device edge must resolve through `env(safe-area-inset-*)`, not a bare pixel guess:
  - TabBar bottom padding: `env(safe-area-inset-bottom, 22px)`.
  - BottomSheet (and BottomSheet-shaped overlays) bottom padding: `calc(30px + env(safe-area-inset-bottom))`.
  - Update toast: as above.
  - Sticky screen headers do **not** need a top inset — the OS status bar area is already excluded from the web viewport unless additional edge-to-edge theming is adopted beyond `viewport-fit=cover`.
- **`display-mode` matrix** — behavior is not just mobile-vs-desktop (§5); it also depends on browser-tab vs. installed-standalone, checked via `window.matchMedia('(display-mode: standalone)').matches`. Four combinations, all required:

  | | Mobile | Desktop |
  |---|---|---|
  | **Browser tab** | Install CTA/card can show (per the gating rules above); no safe-area insets applied — the browser chrome (URL bar, nav buttons) already occupies those edges, so `env(safe-area-inset-*)` resolves to 0 in this mode on most browsers, but a build must not add its *own* extra inset padding here since browser chrome already handles it. | Install CTA can show (`beforeinstallprompt` on desktop Chrome/Edge); no safe-area insets (none apply on desktop hardware regardless of mode). |
  | **Installed / standalone** | Install CTA/card is permanently hidden (check `display-mode: standalone` OR `navigator.standalone` on iOS) — never render it once already installed, regardless of dismissal cooldown state. Safe-area insets now apply for real (`env(safe-area-inset-*)` resolves to actual device values: notch/home-indicator) since there's no browser chrome to already account for them. Browser chrome (URL bar, tab strip, back/forward buttons) is entirely absent — the app IS the whole window; TopHeader's back button becomes the only way to navigate back, so it must never be omitted on a screen with real history to unwind. | Same hiding rule for the install CTA. Safe-area insets are a no-op (desktop has none) but the "no browser chrome" rule still applies — no URL bar, so the offline Banner and TopHeader are the user's only wayfinding. |

  Practical rule: gate the install CTA on `!isStandalone` (both the `display-mode` media query and, on iOS, `navigator.standalone`) in every code path, not just the initial render — a user can install mid-session. Gate safe-area padding logic the same way if a build wants to avoid double-padding in browser-tab mode.

---

## 8. Accessibility requirements

- **Headings**: every screen has exactly one `<h1>` (TopHeader's title, or a dedicated heading where there's no TopHeader — Profile needs a visually-hidden `<h1>Profile</h1>`; the auth wordmark on Sign in/Sign up should be promoted to `<h1>`). Profile's three cards get `<h2>` each. BottomSheet's `title` becomes an `<h2>` inside its dialog wrapper. The Add-item review counter ("Reviewing item X of Y") is a live-announcing `<h2>` (`aria-live="polite"`), not a plain `<span>`.
- **Landmarks**: primary nav → `role="navigation" aria-label="Primary"` with `aria-current="page"` on the active item (done). Authenticated shell and auth shell → `role="main"` on their outer containers (done). Offline `Banner` → `role="status" aria-live="polite"` (not yet applied). Every overlay (BottomSheet variants, filter/add sheets) → `role="dialog" aria-modal="true" aria-labelledby="<heading id>"` (not yet applied).
- **Icon-only controls**: every `IconButton` carries a real `aria-label` with a sensible per-icon default, overridable per mount (done).
- **Focus order**: DOM/visual order already match (flex/grid, no stray `tabindex`). Two real gaps: (1) screen transitions must move focus to the new screen's `<h1>` (`tabIndex="-1"` so it's programmatically focusable without joining tab order) so keyboard/AT users aren't left on a control that no longer exists; (2) overlays must trap focus while open (Tab/Shift+Tab cycles within the dialog's focusable descendants), focus the dialog's first focusable child or heading on open, and restore focus to the invoking control on close.
- **`:focus-visible`, not bare `:focus`**: every control listed in §3 currently shows its ring on any focus, including mouse-click focus. Replace with a real `:focus-visible` rule (see `known-gaps.md` §1) so the ring only appears for keyboard/AT navigation.
- **`prefers-reduced-motion`**: the skeleton-pulse pattern is already correctly gated (static `opacity: 0.7` fallback) — ship as-is. Two more animations still need the same gating: the Switch thumb-slide transition (positional, needs an instant-jump fallback) and the boot/splash logo pulse (already gated, confirm it survives the real build's CSS pipeline).
- **Hit targets**: 44×44px minimum everywhere, per §3's pseudo-element pattern.
- **Contrast**: text/background pairs in both theme blocks (§1.2) were chosen for adequate contrast against their paired surface — re-verify numerically (WCAG AA, 4.5:1 body / 3:1 large text) once real type is set, especially `--color-text-secondary` on `--color-surface-sunken`.

---

## 9. Copy conventions

- **Sentence case** everywhere — titles, buttons, labels, empty/error states. Never title case ("Add Your First Item" → "Add your first item").
- **No em dashes.** Use a period, a comma, or two sentences instead.
- **The app speaks as a first-person stylist, not a system.** Copy like "I need a few more pieces to work with", "Ask me to style something and I'll save the looks here", "I couldn't find any clothing in that photo" — the assistant (not "the app" or "we") owns actions and failures. Exceptions are neutral system-level states that aren't the assistant's voice: connection/sync copy ("You're offline…", "That didn't save. Check your connection and try again.") stays impersonal because it's describing device/network state, not a styling decision.
- **The user is addressed as "you"** ("your closet", "your outfits", "your calendar") — never by name in body copy (the name is reserved for the greeting).
- **Greeting is time-of-day-based**, shown as "{greeting}, {name}" on the Recommend screen: **Good morning** (00:00–11:59), **Good afternoon** (12:00–17:59), **Good evening** (18:00–23:59), using the device's local time. The prototype hardcodes "Good afternoon" always — real time-of-day logic is a gap, see `known-gaps.md`.
- **Error copy names the problem and gives one recovery action** — never a bare "Error" or "Something went wrong" alone; pair it with a specific retry/next-step button label ("Retry", "Try again", "Retake photo", "Back to Closet").
- **Empty-state copy explains what would fill the space and how**, then offers the one action that fills it ("No outfits yet. Ask me to style something and I'll save the looks here." + "Go to Styling").
- Button labels are short verb phrases, 1–3 words ("Add your first item", "Try again", "Clear filter") — no punctuation.

---

## Screen anatomy

Extracted directly from the shipped markup — layout structure top to bottom, and card/row internal composition, for the screens with the richest layouts.

### Recommend (Styling)
1. `TopHeader`: title "Styling", subtitle "Ask for an outfit, get cited picks from your closet" (right slot unused here — `TopHeader` takes `flex:1` and two `IconButton`s sit alongside it as siblings in the same row, since a header needs two independent right-side actions). Right-side action pair, 36px each, `gap:6px`: **New chat** (Lucide `square-pen`) then **Chat history** (clock-with-arrow). New chat archives the current thread as a Chat history session (same `startNewChat` used by Chat history's own "New chat" pill) and resets the thread to the greeting state. **Disabled (not hidden)** — same greyed 0.5-opacity/inert treatment as any other disabled `IconButton` — whenever the thread has no user turns yet (fresh greeting or right after a reset): starting a "new" chat from an already-empty thread would silently archive a blank session into Chat history, which is exactly what §9's real-behavior spec forbids. Kept visible-but-disabled rather than hidden so the control's position in the header never shifts.
2. **Hero state** (no messages yet): centered column — 60×60px rounded-square brand mark (own inline glyph, not the full logo), "What to Wear" wordmark (26px/700), greeting line ("{greeting}, {name}", 13px secondary) below it. Under the hero: one assistant welcome bubble (surface-sunken, `14px 14px 14px 4px` radius, i.e. squared top-inline-start-adjacent corner omitted — the tail corner is bottom-inline-start), then a wrapped row of 3 suggestion chips (pill, 10.5px/600, surface-sunken fill, border): "Rainy day commute", "Dinner date outfit", "Business casual".
3. **Chat state** (after first message): scrollable message list. User bubbles: right-aligned, `--color-primary` fill, white text, tail radius `14px 14px 4px 14px` (bottom-inline-end squared). Assistant bubbles: left-aligned, surface-sunken fill, tail radius `14px 14px 14px 4px` (bottom-inline-start squared), containing inline text segments plus inline numbered `citation` Badges. Below an assistant bubble with referenced items: a wrapped row of 56×56px square swatch thumbnails (`radius-sm` 8px, bordered), each tappable → Item detail. Below that, if the reply cites styling rules: a dashed top-border rule list, each row a numbered `--color-primary` digit + secondary-color explanation text. A reply proposing multiple outfits instead renders the **outfit suggestion pager** (its own card variant, not the Outfits-gallery card — see §3): a swipeable card per suggestion, each with its own header (title/meta + a dedicated favorite heart), its own citation-bearing reasoning block and rule list, its own thumbnail row, and its own thumbs-up/down feedback footer; a prev/next + "X of Y" control row sits below the card track, hidden entirely at a single suggestion. Transient row: "Thinking…" (regular chat acknowledgement only — the multi-outfit generation's own loading treatment is the pager's inline skeleton card, not this trailing caption).
4. Below the message list: a calendar-context line — "Style for an event from calendar" link (not yet picked) or "Styling for {event} · Change" (picked, with a small calendar glyph).
5. "Start styling" full-width primary button appears once the user has sent a message, with a "Uses everything you have told me so far" caption beneath.
6. Pinned bottom: pill-shaped input bar (surface, bordered, fully rounded) — single-line text input "Style me…" + circular 28px send button (primary fill, up-arrow glyph).

### Closet
1. Sticky header block: `TopHeader` (title "Closet", subtitle = item count text), then a wrapped row of category `Chip`s: All, Tops, Bottoms, Outerwear, Shoes, Accessories.
2. **Grid**: 2 columns (mobile) of square-ish tiles, 120px tall, `radius-md` (14px), `--color-surface-sunken`/background diagonal-stripe placeholder fill (stand-in for the item photo), 1px border, monospace debug label centered (replace with the real photo — no title/meta text is overlaid on the tile itself in the current markup; the item's name/category only appear once opened in Item detail).
3. "Load more" pattern: a text button below the grid once more items exist beyond the initial page, with a "Loading more items…" caption during fetch — not infinite scroll, a manual button tied to `onScroll` proximity.
4. At desktop, this list sits in the wide list pane beside an Item-detail pane (placeholder copy "Select an item from your closet to see its details." when nothing is selected).

### Item detail
1. Sticky header: `TopHeader` (title "Item details", back arrow, right slot = `icon` "dots" → opens the item-menu `BottomSheet`).
2. Full-width photo block, 220px tall, `radius-md`-plus (16px), same diagonal-stripe placeholder treatment as the Closet tile, centered monospace debug label.
3. Below the photo, a single `--color-surface` card (`radius-md`, bordered, 16px padding) listing fields **top to bottom** as label (10px/600 secondary) + value (12.5–13px) pairs: Name (13px/700, largest), Category, Group, Fabric, Color, Notes (line-height 1.5, can wrap multiple lines). No image gallery, no size/worn-count/favorite display on the page itself.
4. **On-page actions**: none besides the overflow trigger — Favorite, "Log as worn today", Edit, and Delete all live in the overflow `BottomSheet` opened from the dots icon, not as inline buttons on the page. Choosing Edit swaps the read-only card for an editable form (same field order, `Chip`s for Category, text inputs for the rest) ending in a full-width "Save changes" button.

### Outfit detail
1. Sticky header: `TopHeader` (title = outfit title, subtitle = date, back arrow, no right slot of its own) with two direct-action icon controls as siblings at the far right: a favorite heart (outline/filled, 44px hit area, `aria-label` "Save outfit"/"Unsave outfit" — a second entry point to the same favorite state the overflow sheet's row toggles, kept in sync) then the "⋯" overflow trigger (44px hit area, `aria-label` "More options") → outfit-menu `BottomSheet`.
2. Single `--color-surface` card (`radius-lg`, 18px padding) containing, top to bottom: (a) the item grid — **significantly larger tiles than any other surface**, since this is the one screen where the user is examining the garments themselves rather than scanning a list: a CSS grid, square tiles (`aspect-ratio:1`, `radius-md` 14px), **2 columns at mobile** (each tile ≈ half the card's content width) wrapping to more rows as needed, **3 columns at tablet/desktop** (more columns holds tile size roughly steady rather than letting 2 columns stretch wide) — no scroll, no cap, no chip (see **Item count & overflow** above for why this surface never caps); (b) the styling description as **plain text directly on the card** (no nested tinted surface — matches the chat outfit card's treatment) with inline numbered citation Badges (this is now citations' **only** home — see § Badge); (c) below a dashed top border, the full numbered styling-rules list (same treatment as Recommend's chat rules, unchanged); (d) a second dashed divider, then a "Match breakdown" section: a "Match level: {label}" row using the same pill component as the chat/gallery cards (so all three surfaces render the overall label identically), then the per-dimension bars (unchanged — `--color-primary` fill, `--color-surface-sunken` track, one per sub-score, § Scores).
3. **On-page actions**: none inline — "Log as worn today", Edit title, Delete all live in the overflow `BottomSheet`. Favorite is the one exception (see Outfits below): it's a direct heart affordance on the gallery card, not routed through the sheet at all on either surface. (It's Outfit *detail* that keeps the page free of favoriting/other actions beyond the header's overflow menu.)

### Outfits (gallery)
1. Sticky header: `TopHeader` (title "Outfits", subtitle = count text), then a "Filter & sort" pill button (icon + label + a small circular count badge when facets are active) and a "Clear" text link shown only when filters are active. **Icon unification:** this trigger uses the same Lucide `sliders-horizontal` glyph as `IconButton`'s `filter` keyword (§3) — one filter icon across the app, not a second distinct glyph.
2. **List** (not a strict image grid): vertically stacked cards, `radius-lg` (16px), `--color-surface` fill, bordered, 14px padding, `gap: 12px` between cards. Each card, top to bottom:
   - Header row: title (13px/700, truncates with ellipsis) with the match label immediately to its right as a small pill (same treatment as the chat outfit card's pill — `--color-accent-soft` fill, `--color-primary` text, `radius-pill`, 10.5px/700), then a flexible spacer, then two direct-action icon controls at the far right: a favorite heart (outline/filled, tappable — a **second, direct entry point** to the same favorite state the overflow sheet's "Favorite"/"Unfavorite" row toggles, kept in sync since both write the same field) and the "⋯" overflow trigger (opens that card's menu `BottomSheet`). Both icon controls carry the standard 44px hit-area pseudo-element and a descriptive `aria-label` ("Save outfit"/"Unsave outfit", "More options"). Date ("Today", "Jul 20") sits on its own line directly below the title row. Title has an **inline edit mode** (tap into rename): swaps the title for a text input plus a small "Done" pill button, still showing the date beneath — this is on-card, not in the sheet.
   - Item row: up to **4** real thumbnails at 4 or fewer items; past 4, the first **3** real thumbnails plus a "+N" chip in the 4th slot (52px, no scroll, no wrap, never more than 4 slots) — see **Item count & overflow** above — same tappable-to-Item-detail pattern as Recommend for real thumbnails; the overflow chip taps through to Outfit detail instead.
3. At desktop, this list is the wide list pane beside an Outfit-detail pane (placeholder "Select an outfit to see its details." when nothing selected).

### Calendar
1. Sticky header: `TopHeader` (title "Calendar events", back arrow, no right slot).
2. **Disconnected state**: a single centered `--color-surface` card (`radius-md`, 22px/18px padding) — 44px icon tile (calendar glyph) centered, "Connect your calendar" heading (13px/700), explanatory body (11.5px secondary), full-width primary "Connect Google Calendar" button.
3. **Connected, has events**: a "Pick an upcoming event to style for." caption line, then a vertically stacked list of event rows (`radius-md` 14px, surface fill, bordered, 14px padding, `gap:10px`): each row shows the event title (12.5px/700) on its own line, then a meta line "{time} · {location}" (10.5px secondary) below it. Once an event is picked, all rows go `disabled` (opacity 0.5, `cursor:not-allowed`) — the picked context surfaces back on the Recommend screen, not as a highlighted row here.
4. **Connected, no events**: empty-state copy + a "Style something" button (bypasses calendar, goes to Recommend) instead of the event list.

### Chat history / Session detail
1. **Chat history** — sticky header: `TopHeader` (title "Chat history", back arrow, right slot = `pill` "New chat"). Below it, a vertically stacked list of session rows (`radius-md` 14px, surface fill, bordered, 14px padding, `gap:10px`), each row: top line = session preview text (12.5px/700) with the date (10px secondary) right-aligned on the same line; second line = message-count text (10.5px secondary); optional third line, only if the session produced outfits — an outfit-count line in `--color-primary` (10px/700).
2. At desktop, this list sits beside a Session-detail pane (placeholder "Select a conversation to view it." when nothing selected).
3. **Session detail** — sticky header: `TopHeader` (title "Conversation", subtitle = session date, back arrow, no right slot). Below it, the full read-only message thread (same user/assistant bubble treatment as Recommend, including citation Badges — but no item-thumbnail rows or rule lists in the archived view). Below the thread: a full-width primary "Continue conversation" button (resumes into Recommend), and — only if the session produced outfits — a second full-width secondary button "{outfit count} → View in Outfits" beneath it.

---

## Image treatment

No real photos exist in the prototype — every "photo" is the same diagonal-stripe placeholder: `repeating-linear-gradient(135deg, var(--color-surface-sunken) 0/8px, var(--color-background) 8px/16px)` with a centered monospace debug label, on a 1px `--color-border` outline. Radius and box size vary **per context, as literal pixel values, not a shared token**:

| Context | Box | Radius | Aspect ratio |
|---|---|---|---|
| Closet grid tile | fixed `height: 120px`, width = grid column (`1fr`, so width flexes 1:1 with viewport/column count) | 14px | **Not fixed** — mobile 2-col ≈ square, but at tablet/desktop the grid switches to `repeat(auto-fill, minmax(130–140px, 1fr))` while height stays a literal 120px, so tiles get wider (less square) as columns narrow toward the minmax floor. A real build should decide a fixed `aspect-ratio` (e.g. `1/1`) instead of carrying this height-only rule forward. |
| Item detail hero photo | full-width, fixed `height: 220px` | 16px | Flexes with viewport width, fixed height — effectively widescreen on desktop, near-square on narrow mobile. |
| Add-item upload dropzone | full-width, fixed `height: 220px` | 16px | Same as item detail hero. |
| Add-item review-card photo | full-width, fixed `height: 150px` | 16px | Same flexing behavior, shorter box. |
| Item thumbnail (chat, Outfits gallery card — unified) | fixed `56×56px` | 8px (`radius-sm`) | Square, fixed. |
| Item thumbnail (Outfit detail — deliberately larger) | fraction-based, `aspect-ratio:1` — **2-column grid at mobile** (≈ half the card's content width each), **3-column at tablet/desktop** | 14px (`radius-md`) | Square, scales with column width — the one screen where garments are the focus rather than a scanned list, so tiles dominate instead of staying a fixed small size. |

**Dark mode note:** the placeholder's two stripe colors (`--color-surface-sunken`, `--color-background`) are both near-adjacent low-contrast neutrals in *both* themes (light: `#EFEADD` vs `#E6E1D6`; dark: `#201C28` vs `#1C1822`) — the pattern is intentionally subtle, not swapped or restyled for dark mode, and needs no separate dark variant. Once real photos replace the placeholder, this striped pattern and its debug label should be deleted outright, not preserved as a loading state (the skeleton blocks below are the actual loading treatment).

## Per-screen skeleton layouts

Every skeleton block is a flat `opacity: 0.7` `--color-surface-sunken` rectangle (pulsing opacity 0.55↔1 only when `prefers-reduced-motion: no-preference`, per §8) shaped to approximate its screen's real content:

| Screen | Skeleton shape |
|---|---|
| Recommend | Two left-aligned chat-bubble-shaped bars, stacked with `gap:10px`: 70% width × 56px tall, then 45% width × 32px tall (approximates a welcome bubble + a suggestion chip). |
| Closet | A 2-column grid of four `120px`-tall blocks at `14px` radius — matches the real tile grid exactly (2 rows × 2 cols). |
| Item detail | One `--color-surface` card holding three pulsing bars stacked with `gap:12px`: 60% / 40% / 80% width, each `14px` tall, pill-radius — approximates the Name/Category/Notes field stack (not a full field-by-field skeleton). |
| Add item | A single `220px`-tall block at `16px` radius standing in for the upload photo. |
| Outfits | Two `100px`-tall blocks at `16px` radius, stacked with `gap:12px` — approximates two collapsed outfit cards (not their internal thumbnail rows). |
| Outfit detail | One card: a `2`-column grid of `aspect-ratio:1` blocks at `14px` radius (the item thumbnails, sized to match the real grid's mobile column count) then a `70px`-tall bar (the description block). |
| Calendar | Two `56px`-tall blocks at `14px` radius, stacked with `gap` — approximates two event rows. |
| Chat history | Two `64px`-tall blocks at `14px` radius — approximates two session rows. |
| Settings | Two `100px`-tall blocks (`--radius-md`) then one `60px`-tall block, stacked with `--space-lg` gap — approximates the Account / Connected-accounts / Notifications cards. |
| BottomSheet (any) | Three pulsing bars at 85% / 65% / 75% width, `14px` tall each, pill-radius, stacked with `--space-md` gap. |

## Chat input behavior

The Recommend and Session-detail composer is a **single-line `<input>`, not a growing textarea** — long messages scroll horizontally within the field rather than wrapping. No `maxlength` is set in the prototype (unbounded). Enter key submits (`keydown` → prevent default → send); there is no Shift+Enter-for-newline behavior since it's single-line.

**Observed (prototype):** the send button disables only on `isOffline`; the text input itself is never disabled while a prior message is `sending` (shows a "Thinking…" bubble) or `styling` (shows a "Styling your outfit…" bubble) — a user can keep typing and re-submit before the assistant replies, which allows a double-send.

**Intended (production):** disable both the input and the send button whenever `sending || styling` is true (in addition to `isOffline`), and show a visible sending/waiting affordance on the send button itself (e.g. swap the arrow glyph for a small spinner) so the disabled state reads as "in progress," not "broken." Re-enable both the instant the assistant's reply lands. This closes the double-send gap the observed behavior allows — build the intended version, not the observed one.

## BottomSheet & toast motion

**BottomSheet has no open/close transition in the prototype today** — it mounts and unmounts instantly via conditional rendering (no slide, no backdrop fade). Recommended real-build motion, built from the existing tokens (§1.1), to add without changing any visual/layout spec above:
- **Backdrop**: fade `opacity 0→1`, `var(--motion-duration-base) var(--motion-easing-decelerate)` on open; reverse (`var(--motion-duration-fast) var(--motion-easing-accelerate)`) on close.
- **Panel**: translate `translateY(100%) → translateY(0)` (mobile bottom-anchored) or `scale(0.96) → scale(1)` + fade (tablet+/centered-dialog mode), `var(--motion-duration-base) var(--motion-easing-decelerate)` on open; reverse at `var(--motion-duration-fast) var(--motion-easing-accelerate)` on close — closing is snappier than opening, consistent with the `fast`/`base` split already established by the token names.

**No toast exists anywhere in the prototype** (the update toast is a PWA surface described only prospectively in §7/`known-gaps.md` §-2 — there is no built component to extract motion from). Recommended spec, same token logic as the sheet: slide up from `translateY(100%)` + fade in, `var(--motion-duration-base) var(--motion-easing-decelerate)`; auto-dismiss or manual-dismiss should reverse at `var(--motion-duration-fast) var(--motion-easing-accelerate)`.

## Date & time formats

**Calendar event rows**: `{relative day}, {h:mm AM/PM}` as a single string, e.g. "Today, 7:30 PM".

**Observed (prototype):** this exact string is hardcoded in mock event data — there is no date-formatting logic behind it.

**Intended (production):** compute the relative-day label from the event's real timestamp (Today / Tomorrow / weekday name for the next ~6 days / short date beyond that — a common convention) plus a locale-aware time format, so the label always reflects the actual event date rather than a fixed string.

**Chat history session rows**: a `dateLabel` string shown at 10px, secondary color.

**Observed (prototype):** every session's `dateLabel` is hardcoded to the literal string `"Today"` — mock sessions carry no real archival timestamp.

**Intended (production):** derive `dateLabel` from the session's actual archived-at timestamp using the same relative-date convention as Calendar above (Today / Yesterday / weekday / short date).

**Session detail subtitle**: reuses the same `dateLabel` string as its list row (not reformatted or expanded) — this pass-through is the intended behavior once `dateLabel` itself is computed correctly per the fix above.

**Settings' birth date** is the one real date-formatting example in the codebase and needs no fix: `new Date(...).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })` → e.g. "January 1, 1990" (locale-aware long form, no fixed format string).

## Card title truncation rule

**Single-line ellipsis truncation** (`white-space: nowrap; overflow: hidden; text-overflow: ellipsis`) applies to: `TopHeader` titles/subtitles (§3), and Outfit-gallery card titles.

**Observed (prototype):** the Chat-history session preview line and the Item-detail Name field have no overflow rule at all — a long value wraps or overflows unstyled, inconsistent with every other title-like text in the app.

**Intended (production):** apply the same single-line-ellipsis rule to both, for consistency with every other card/row title in the system. Body/description text (chat bubbles, outfit descriptions, empty/error copy, Settings field values) should remain untruncated in both observed and intended behavior — it wraps normally at its stated line-height (§2); only title-like, single-line fields get ellipsis truncation.

---

## Open questions

Minor UI ambiguities left after two full cold reads — none block implementation; decide these during build and move on:

- **Category chip icons**: are Closet category `Chip`s (Tops/Bottoms/etc.) text-only everywhere, or do they ever carry a small leading icon?
- **Body-shape illustrations**: the 5-option body-shape selector (Hourglass, Pear, Rectangle, Apple, Inverted triangle) needs a stroke weight/size spec for its line-art silhouettes if rebuilt without the source SVGs.
- **Google "G" button**: standard four-color Google mark on Sign in/Sign up — confirm whether pixel-exact adherence to Google's brand guidelines is required or a close approximation is acceptable.
- **Review progress bar fill**: does the "Reviewing item X of Y" progress bar animate/ease between steps, or jump instantly to the new percentage?
- **TabBar exact dimensions**: the bar's own height (mobile) and the FAB's exact diameter aren't pinned down numerically (only the rail's 76px and sidebar's 240px are).
- **Settings Edit/Done toggle**: does the toggle button change color/style while in "editing" mode, or only its label swaps from "Edit" to "Done"?
- **Inline favorite toggle**: does tapping the heart glyph on an Outfits gallery card toggle favorite directly, or is favoriting only reachable via the overflow sheet?
- **"Enter manually" flow** (Add item, no-clothing-detected state): does it open the same review form with blank fields, or a distinct manual-entry flow?
- **Citation Badge consistency**: confirm the numbered citation pill (§3 Badge) uses one shared visual spec across chat, Outfit detail, and Session detail — the doc assumes this but never states it as a hard constraint.
- **Pager control row dimensions**: exact px height/width of the prev/next 32px circles relative to the card — is the control row full-width, centered, or card-width?
- **Pager ready-state timing**: what triggers the loading→ready transition timing/animation, if any, beyond "appears immediately"?
- **Pager slide animation**: does the mobile transform-slide between cards have a duration/easing, or is it instant?
- **Pager scroll-snap overscroll**: on tablet/desktop's native scroll-snap track, does dragging past the last/first card bounce, or hard-stop?
- **Sub-score bar labels**: Outfit detail's per-dimension bars ("weather, formality, style, similar") — what's the exact display label text for each (e.g. "Weather fit" vs "Weather")?
- **Card corner radius/padding parity**: are the Outfits gallery card's and chat card's corner radius, padding, and border values identical, or do they diverge by context?
- **"+N" overflow chip typography**: does it show anything beyond the "+N" text — same font size/weight as the rest of the row?
- **Favorite heart glyph spec**: exact stroke width and fill treatment (outline vs. filled) — a specific icon set's default weight, or a custom weight?
- **Pager/card gap consistency**: exact spacing between the pager's control row and the card above it, and between cards in the Outfits list vs. the chat pager's internal spacing — is 12px used everywhere or only in Outfits?
- **Pressed states for pager controls**: what does a pressed/active (not hover/focus) state look like for the prev/next arrows and the thumbs buttons?
- **Pager arrow-key navigation**: do ←/→ keys page the pager when the control row is focused, or is Tab+Enter the only path?
- **Pager loading microcopy**: is there a text label alongside the loading skeleton, or skeleton-only?
- **Favorite aria-label wording per surface**: does the heart's aria-label use identical wording ("Save outfit"/"Unsave outfit") across all three surfaces, or context-specific variants (e.g. "Save suggestion")?

---

## Prototype scaffolding — do not ship

The following exist only to author/demo this prototype and must be removed before any of the above ships:

- **Dev state-override panel** (dashed-border panel, screen/state pickers) and everything feeding it: `devOverrideScreen`/`devOverrideState` state, `devFor()`, `handleDevScreenChange`/`handleDevStateChange`/`clearDevOverride`/`retryDev`, `DEV_SCREEN_MAP`/`DEV_STATE_OPTIONS`. Replace with real loading/error/empty conditions from an actual data layer.
- **The viewport-tier and direction (`dirMode`) dev selectors**, and the fixed device-bezel wrapper (`ios-frame.jsx`) they drive — presentation-only, not part of the shipped responsive mechanism (§5 already describes the real one).
- **The floating theme toggle button** — a real build reads `prefers-color-scheme` at boot plus a persisted user override; it doesn't need a manual dev toggle in the UI.
- **All `!important` layout overrides** tied to the dev viewport/bezel simulation — a real responsive build using actual viewport media queries won't need `!important` to win against a simulated container.
- **Inline-style workarounds** that exist only because this authoring tool has no compiled CSS pipeline — the token values and states are real (§1–§3); their *expression* as literal inline styles is not the target architecture. Implement them as an actual CSS/tokens pipeline (or CSS-in-JS) reading the same semantic variable names.

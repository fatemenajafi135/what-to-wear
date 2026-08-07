# Handoff — Feature 001: App shell, tokens, component library, PWA basics

**From:** tech lead · **Status:** ready to start · **Branch:** cut from `rebuild`

This is the foundation slice. Everything after it consumes what you build here, so the cost
of getting a token name or a component API wrong is paid seven more times. Take the extra
day.

---

## 1. Mission

Stand up the Next.js application shell, the design-token pipeline, and the shared component
library, plus the PWA basics that affect layout and routing. **No product screens, no data,
no auth.** Every route you create is a stub that renders its chrome and its empty state.

---

## 2. How to run this

Start from `rebuild`. Spec Kit cuts the feature branch for you.

```
/speckit-specify  →  /speckit-clarify  →  /speckit-plan  →  /speckit-tasks
                  →  /speckit-analyze  →  /speckit-implement
```

Merge back into `rebuild` by PR when done.

The Spec Kit templates have been reviewed and corrected against the constitution — two of
them offered a `ios/` + `android/` project layout, which Principle IX forbids. `plan-template.md`
now carries the ten explicit Constitution Check gates and the fixed repository layout. Fill
those gates in honestly; they are the review checklist your PR will be read against.

---

## 3. Read first, in this order

| # | File | What to take from it |
|---|---|---|
| 1 | `.specify/memory/constitution.md` | Binding. Principles **VIII, IX** and **II** govern this slice. |
| 2 | `design/design-system.md` §1–§3, §5, §6, §8 | Tokens, the 11 components with full state matrices, responsive tiers, state copy, accessibility. |
| 3 | `docs/design-decisions.md` | **Equally binding.** Resolves what §2 leaves broken. §1 is the form-control spec that does not exist in the design system at all. |
| 4 | `design/known-gaps.md` §-2, §1, §3 | The full manifest JSON, theme-color meta tags, safe-area audit, `:focus-visible`, reduced-motion. |
| 5 | `design/design-system.md` "Screen anatomy", "Per-screen skeleton layouts" | Shapes for the skeleton states you will implement per screen. |

`design/prototype/` is reference only. Read it to understand intent. **Never copy code from
it.** Nothing under `design/prototype/_scaffolding/` may appear in the product — that is a
constitutional rule (VIII), not a style preference.

---

## 4. In scope

### 4.1 Token pipeline

The three-layer architecture from §1: system tokens → semantic tokens → theme blocks. Both
light and dark blocks. `data-theme` on the document root.

- **Type scale comes from `docs/design-decisions.md` §6, not from `design-system.md` §2.**
  The design system's sizes are superseded — they fall below the iOS and Material minimums.
  Ten tokens, two tiers breaking at 1024px. After this, **no component may contain a raw hex
  or a magic pixel value.**
- **Boot theme is a known gap you must close:** read `prefers-color-scheme` *before first
  paint*, falling back to a persisted user override. The prototype always booted light.
  Getting this wrong produces a visible flash on every cold start.
- Font: Instrument Sans (400/500/600/700) from Google Fonts, with the system fallback stack
  in §1.

### 4.2 Component library

Eleven from `design-system.md` §3 — Button, IconButton, Chip, Badge, Switch,
SegmentedControl, TopHeader, TabBar, BottomSheet, AvatarInitial, Banner — plus the five from
`design-decisions.md` §1 — Input, Textarea, Select, DatePicker, TagInput.

Each ships its **full state matrix**, not just its default: hover (pointer only), active,
focus-visible, disabled, and where specified loading, error and empty.

**The outfit suggestion pager is out of scope** — it is chat-specific and belongs with the
styling feature.

### 4.3 App shell and routing

- Route stubs for `/recommend`, `/closet`, `/outfits`, `/profile`, `/profile/settings`,
  `/add`. Each renders its chrome and its empty state. No data.
- Which chrome persists across navigation, and which remounts.
- **Responsive chrome, CSS-only** — bottom tab bar (0–767) → 76px icon rail (768–1023) →
  240px sidebar (1024+). Same routes at every size; only the frame changes (Principle IX).
- Create is **not** a fifth nav destination. It is an overlay launcher, positioned
  differently per tier — see §5's nav-mapping table.
- Focus moves to the new screen's `<h1>` on navigation (`tabIndex="-1"`).

### 4.4 PWA basics

- `app/manifest.ts` — the full JSON is already written out in `known-gaps.md` §-2. Use it.
  **Change only the two `shortcuts` URLs** to `/add` and `/recommend` per
  `design-decisions.md` §9.
- Both `<meta name="theme-color" media="...">` tags — the manifest field alone cannot
  respond to a live theme change.
- `viewport-fit=cover` plus `env(safe-area-inset-*)` on every edge-docked element. The
  safe-area audit in `known-gaps.md` §-2 lists each one and its correct value.
- `/` redirects: signed-out → `/signin`, signed-in → `/recommend`.

**Icons are already done.** `frontend/public/icons/` holds all seven PNGs plus
`favicon.ico` and `apple-touch-icon.png`, generated from `design/assets/mark.svg` and
verified (correct dimensions, maskable content 22.9px clear inside the 80% safe circle, no
alpha on the apple-touch icon). **Do not regenerate them.** The filenames already match the
manifest.

---

## 5. Explicitly out of scope

Auth and the four `/signin` `/signup` `/forgot-password` `/reset-password` screens (002) ·
any real data or API call · closet, outfits, chat, calendar screens (003–006) · **the
service worker, Serwist, caching, and the update prompt (007)** · the install prompt and
permission primers (007) · Apple splash screens (007) · the outfit pager · RTL.

Feature 007 owns everything offline. If you find yourself writing a caching strategy, stop.

---

## 6. Decisions already made — do not relitigate

| Topic | Decision | Source |
|---|---|---|
| Focus ring | `outline` + `outline-offset`, **not** `--shadow-focus-ring`, which is retired. The old recipe rendered an invisible ring on primary buttons. | design-decisions §4 |
| `--color-disabled` | Does not exist and must not be created. Disabled is `opacity: 0.5` + `pointer-events: none`, always. | design-decisions §5 |
| Chat pager thumbnails | 4 / 6 / 7 columns. The design system's "8 columns" needs 490px in a 414px track. | design-decisions §3 |
| Overflow chip | 56px, matching thumbnails. The "52px" is a typo. | design-decisions §10 |
| Reduced motion | Gate all five animations, not the two §8 lists. | design-decisions §10 |
| Match score | Derived from the four sub-scores, never stored. | design-decisions §8 |
| Manifest shortcuts | Real routes `/add`, `/recommend`. | design-decisions §9 |
| Em-dash copy | Three strings are corrected. Use the replacements. | design-decisions §7 |
| Type scale | Rebuilt. `design-system.md` §2's sizes are superseded; minimum text is 11px. | design-decisions §6 |
| Password minimum | 8 characters, with Supabase config raised to match. | design-decisions §1.7 |

---

## 7. Traps

1. **The prototype's responsive mechanism does not carry over.** It demos breakpoints with a
   container query scoped to a fixed device-bezel wrapper, purely for presentation. Use real
   viewport media queries on the app shell. Do not reproduce the bezel, `ios-frame.jsx`, the
   `!important` overrides, the dev state-override panel, the viewport/direction selectors, or
   the floating theme toggle. All are listed under "Prototype scaffolding — do not ship."
2. **`--wtw-proto-inset-top` must not survive.** Production headers use bare
   `env(safe-area-inset-top)` with no floor.
3. **Do not port the simulated status bar's `z-index: 1000`.** On a real device the OS draws
   the status bar in its own layer; there is no app-level element.
4. **Hover only under `@media (hover: hover)`.** Never simulate hover on touch.
5. **44×44px minimum hit target** via the pseudo-element pattern in §3, on every control
   whose painted box is smaller. Skip only controls already ≥44px in both dimensions.
6. **BottomSheet needs real dialog semantics**, which the prototype lacks:
   `role="dialog" aria-modal="true" aria-labelledby`, focus trap, focus restore on close.
7. **Native `<select>` stays native.** Do not build a custom listbox — you lose mobile
   pickers, keyboard behaviour and AT semantics.
8. **Two logo assets, different jobs.** `logo.svg` is a 1264×843 landscape lockup for headers
   and auth. `mark.svg` is the 240×240 square master for icons. Do not use one where the
   other belongs.

---

## 8. Nothing is left open

Every question that was outstanding when this slice was scoped has been decided.
`docs/design-decisions.md` contains no open items. Two of those decisions land directly on
your work:

- **Password minimum is 8 characters** (design-decisions §1.7). Supabase's
  `password_min_length` must be raised from its default of 6 to match, so the server enforces
  what your validation copy claims.
- **The type scale is rebuilt** (design-decisions §6). Do **not** use the sizes in
  `design-system.md` §2 — they are superseded. A uniform ×1.12 multiplier was applied to
  clear the iOS 11pt and Material 14sp floors, preserving every ratio the designer chose, plus
  one step up at 1024px. Ten tokens, two tiers, breaking at 1024px only. **The minimum text
  size anywhere is now 11px, not 10px.**

If you hit something genuinely undecided, §10 tells you what to do with it.

---

## 9. Definition of done

- [ ] Every component renders every state in its matrix, in **both** themes.
- [ ] No raw hex or magic pixel value anywhere in component code — every value reads a token.
- [ ] Lighthouse **Installable** passes. (Offline is 007's gate, not yours.)
- [ ] Keyboard-only pass: every control reachable, focus ring visible on keyboard nav and
      **absent** on mouse click, focus moves to `<h1>` on navigation, focus trapped and
      restored in BottomSheet.
- [ ] Layout holds at 320px, 768px, 1024px and 1440px, with identical routes at all four.
- [ ] `prefers-reduced-motion: reduce` stops all five animations.
- [ ] No flash of the wrong theme on cold start.
- [ ] Real-device check: safe-area insets correct on a notched iPhone in installed
      standalone mode.
- [ ] `eslint`, `tsc --noEmit` and `next build` all clean.

---

## 10. If you find a design gap

`design-decisions.md` exists because the design system has holes. If you hit another one,
**do not invent a value and move on** — that is a Principle VIII violation. Add it to
`docs/design-decisions.md` with your reasoning, flag it in the PR, and raise it. A documented
gap is cheap; an invented value is indistinguishable from a bug six screens later.

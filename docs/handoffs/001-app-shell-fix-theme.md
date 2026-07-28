# Fix brief — boot theme never reads `prefers-color-scheme`

**From:** tech lead · **Follows:** `docs/handoffs/001-app-shell.md` and its completion report
· **Scope:** small, two files · **Branch:** cut from `rebuild` (001 is merged)

Feature 001 was reviewed and merged. Everything else in it verified clean. This is the one
defect found, plus a cost that came with it.

---

## 1. What is wrong

`frontend/lib/theme.ts` sets `DEFAULT_THEME = "light"`, and `prefers-color-scheme` is read
nowhere in the application. **A first-time visitor whose OS is in dark mode sees the light
theme**, and nothing will ever correct it, because no theme toggle ships in this slice to
write the cookie.

That is precisely the gap `design/known-gaps.md` §-2 names:

> **Theme not synced to system preference at boot (separate, real gap)**: `state.theme`
> always initializes to `'light'` regardless of OS preference — nothing reads
> `prefers-color-scheme` at boot.

and which `docs/handoffs/001-app-shell.md` §4.1 asked to close. The rebuild currently
reproduces the prototype's exact bug.

## 2. Why the original reasoning missed it

`specs/001-app-shell/research.md` argues this carefully and honestly — the problem is the
options it weighed. "Alternatives considered" lists an inline blocking `<script>` reading
`localStorage` + `matchMedia`, and `next-themes`. Both are rejected, correctly, for
reintroducing a flash or pulling in a dependency.

**Neither of those is the solution. CSS is.** A media query resolves before first paint by
definition — there is no script, so there is nothing to flash. The research never evaluated
a pure-CSS path, so a sound argument reached a wrong conclusion.

Two claims in that document to correct while you are in there:

- *"a client-side `matchMedia` read reintroduces the exact flash"* — true of JavaScript,
  irrelevant to CSS.
- *"cannot help SSR'd content match on the very first response byte"* — this conflates HTML
  with custom-property values. The markup is theme-agnostic; only CSS variables differ.
  There is nothing to mismatch, and therefore no hydration risk.

## 3. The second cost

`resolveTheme()` calls `cookies()` in the root layout, which opts **the entire application**
out of static rendering. Every route reports `ƒ (Dynamic)` in the build output:

```
┌ ƒ /          ƒ /add        ƒ /closet      ƒ /outfits
├ ƒ /profile   ƒ /profile/settings          ƒ /recommend
```

For a PWA that wants fast TTFB and CDN-cacheable HTML, that is a real price — and it was
paid to solve a problem that costs nothing in CSS. These stub routes have no per-request
data; they should be static.

## 4. What to do

**Recommended — `light-dark()`.** One declaration per token, no duplicated block, system
preference honoured automatically, and an explicit override that still wins:

```css
:root {
  color-scheme: light dark;
  --color-primary:    light-dark(#4b2e52, #c9a6d6);
  --color-background: light-dark(#e6e1d6, #1c1822);
  /* …one line per themed token… */
}
[data-theme="light"] { color-scheme: light; }
[data-theme="dark"]  { color-scheme: dark;  }
```

Every themed token in `themes.css` is a colour (including the `rgba()` shadow colours), so
all of them qualify. `--shadow-xs/sm/md` compose unchanged, since they reference the colour
variables rather than restating them.

**Conservative alternative**, if you would rather not depend on `light-dark()`: keep the
existing blocks and add a third that applies the dark values when no override is present.

```css
@media (prefers-color-scheme: dark) {
  :root:not([data-theme]) { /* dark values */ }
}
```

This duplicates the dark block, which is a drift risk worth a comment, but it is plain CSS
with no feature dependency. **Either approach is acceptable** — the acceptance criteria in
§5 are what matter, not the mechanism.

**Then restore static rendering.** Remove the `resolveTheme()` call from
`frontend/app/layout.tsx` so `cookies()` is no longer invoked. No toggle exists to write the
cookie, so nothing is lost today. Either keep `lib/theme.ts` with a comment saying it is
wired up when a theme control ships, or delete it and re-add it then — your call, but do not
leave an unexplained unused module.

**Update the research record.** Amend `specs/001-app-shell/research.md`'s "Boot-time theme"
decision rather than deleting it. The reasoning is worth preserving; it should end with what
was missed and why the conclusion changed. A decision record that quietly rewrites itself
teaches nobody.

## 5. Definition of done

- [ ] With OS/browser set to dark and **no cookie present**, the app renders dark on first
      paint. Verify with `page.emulateMedia({ colorScheme: 'dark' })`.
- [ ] With OS set to light and no cookie, it renders light.
- [ ] An explicit `data-theme` on `<html>` still overrides the system preference in both
      directions — this is what a future toggle depends on.
- [ ] **No flash.** Nothing repaints from one theme to the other after first paint.
- [ ] `next build` shows the stub routes as `○ (Static)`, not `ƒ (Dynamic)`.
- [ ] `frontend/e2e/theme-boot.spec.ts` gains coverage for the no-cookie dark case. It
      currently only exercises the cookie path, which is why this shipped.
- [ ] `tsc --noEmit`, `eslint`, `next build`, Vitest and Playwright all still clean.
- [ ] `research.md` amended, not rewritten.

## 6. Not in scope

Do not build a theme toggle. None is specified in `design/design-system.md` — not in the
sixteen components, not in the Settings section list — and adding one would invent UI the
design system does not contain, which is a Principle VIII violation in the opposite
direction. The original agent was right about that, and right to say so.

---

## 7. For the record

The rest of feature 001 was verified independently and held up: type scale exact, all five
form controls correctly pinned to 16px against iOS auto-zoom, focus ring using
`outline`/`outline-offset`, no prototype scaffolding leaked, icon set untouched, dev catalog
genuinely gated. `/speckit-analyze` caught two spec gaps before coding, the test suite caught
two real bugs, and the completion report named what it skipped instead of claiming a clean
sweep. This fix is a miss in one decision, not a pattern.

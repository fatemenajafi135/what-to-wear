# Quickstart: validating the app shell

Run these after implementation to confirm the feature meets its spec and the handoff's
definition of done (`docs/handoffs/001-app-shell.md` §9). Each check links back to the
requirement it proves.

## Setup

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000`.

## 1. Chrome and routing (FR-001, FR-002, FR-003, SC-001)

- Resize the browser to 320px, 768px, 1024px and 1440px. At each width, confirm Recommend,
  Closet, Outfits and Profile are all reachable and the chrome matches: bottom bar (<768),
  icon rail (768–1023), labelled sidebar (1024+).
- Confirm "Create" never appears as a fifth nav item, and its shape changes per tier (FAB /
  icon button / labelled pill).
- Visit each stub route directly (`/recommend`, `/closet`, `/outfits`, `/profile`,
  `/profile/settings`, `/add`) and confirm each renders its chrome + defined empty state with
  no console errors and no data fetch.
- Navigate between routes and confirm focus lands on the new screen's `<h1>` each time.

## 2. Component catalog (FR-005a, FR-006, FR-007, SC-002)

```text
http://localhost:3000/dev/components
```

- Confirm this route 404s when built with `NODE_ENV=production` (`npm run build && npm start`).
- In dev mode, cycle every state of all 16 components in both themes (toggle via your
  browser's dark-mode emulation, or by setting `data-theme="light"`/`"dark"` on `<html>` in
  devtools). Confirm no state is visually broken and nothing reads a raw color/pixel value
  (spot-check by searching component CSS for hex codes or bare `px` literals outside the
  token files).
- Confirm every control smaller than 44×44px still has a 44×44px click/tap target (browser
  devtools box model on the pseudo-element).

## 3. Keyboard and focus (FR-008, FR-009, FR-010, SC-003)

- Tab through an entire stub screen. Every interactive control must be reachable, in visual
  order.
- Confirm the focus ring appears on Tab-focus and is absent on mouse click, for at least one
  instance of each: Button, IconButton, Chip, Switch, Input.
- Open a BottomSheet (via the catalog route or an item/outfit menu once wired). Confirm Tab
  cycles only within it, Escape closes it, and focus returns to the invoking control.

## 4. Reduced motion (FR-011, FR-018)

- Enable `prefers-reduced-motion: reduce` at the OS level (or Playwright's
  `page.emulateMedia`).
- Confirm the skeleton pulse, Switch thumb-slide, boot logo pulse (`app/loading.tsx`), and
  BottomSheet's open/close transition all render as static, with no animation.
- Throttle the network (devtools) to force `app/loading.tsx` to appear on a navigation, and
  confirm the mark/wordmark render correctly on the background token in both themes.

## 5. Theme boot (corrected by `docs/handoffs/001-app-shell-fix-theme.md`, FR-005, SC-005)

- Force the OS/browser to dark mode with no `data-theme` override set anywhere: reload and
  confirm dark renders on the very first frame — this is a pure CSS `light-dark()` resolution
  (`styles/themes.css`) against `prefers-color-scheme`, so there is no server call or script
  to wait on.
- Force the OS/browser to light mode the same way: confirm light renders.
- In devtools, set `data-theme="dark"` on `<html>` while the OS is light (and the reverse):
  confirm the explicit attribute wins both times — this is the override a future theme
  toggle depends on.
- Repeat several cold reloads split across forced light/dark; confirm 0 show a flash. Since
  the whole mechanism is CSS with no script involved, there is no code path left that *could*
  flash — this is a sanity check, not a search for a bug.
- Run `npm run build` and confirm the stub routes (`/recommend`, `/closet`, `/outfits`,
  `/profile`, `/profile/settings`, `/add`) report `○ (Static)`, not `ƒ (Dynamic)` — the root
  layout no longer calls `cookies()`.

## 6. PWA basics (FR-012, FR-013, FR-014, FR-015, SC-004, SC-006)

- `curl -s localhost:3000/manifest.webmanifest | jq` — confirm it matches
  `contracts/manifest.md` exactly, including the two shortcut URLs (`/add`, `/recommend`).
- View source on `/` and confirm both `theme-color` meta tags are present with the
  `prefers-color-scheme` media queries.
- **Lighthouse's PWA category/audits (`installable-manifest`, etc.) have been removed from
  the tool as of the version current at this writing (13.4.1)** — `--only-categories=pwa`
  errors with "unrecognized category." Verify installability manually instead: confirm
  `manifest.webmanifest` has `name`, `short_name`, `icons` (192 + 512), `start_url`, and
  `display: "standalone"` (all present per `contracts/manifest.md`), served over HTTPS (or
  localhost). Chrome DevTools' Application → Manifest panel also flags any manifest error
  directly. Note: this slice ships no service worker (feature 007's scope) — whether
  `beforeinstallprompt` actually fires end-to-end depends on the browser's current
  criteria and cannot be fully confirmed until 007 lands.
- Navigate to `/` and confirm it redirects to `/recommend`.
- On a real notched iPhone, install to home screen, launch standalone, and confirm the
  TabBar and any open BottomSheet clear the safe-area insets with no overlap.

## 7. Lint and build gates (constitution Quality Bar)

```bash
npm run lint
npm run tsc -- --noEmit
npm run build
```

All three must be clean with zero errors before this feature is considered done.

# Contract: PWA manifest and boot-theme surfaces

## `app/manifest.ts`

Returns exactly this shape (Next.js `MetadataRoute.Manifest`), sourced verbatim from
`design/known-gaps.md` §-2 with the two `shortcuts[].url` values changed per
`docs/design-decisions.md` §9:

```json
{
  "name": "What to Wear",
  "short_name": "What to Wear",
  "id": "/",
  "start_url": "/?source=pwa",
  "scope": "/",
  "display": "standalone",
  "orientation": "portrait",
  "lang": "en-US",
  "dir": "ltr",
  "background_color": "#E6E1D6",
  "theme_color": "#4B2E52",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
    { "src": "/icons/icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ],
  "shortcuts": [
    { "name": "Add an item", "short_name": "Add item", "url": "/add", "icons": [{ "src": "/icons/shortcut-add.png", "sizes": "96x96", "type": "image/png" }] },
    { "name": "Get a recommendation", "short_name": "Recommend", "url": "/recommend", "icons": [{ "src": "/icons/shortcut-recommend.png", "sizes": "96x96", "type": "image/png" }] }
  ]
}
```

All icon files referenced already exist in `frontend/public/icons/` and must not be
regenerated (handoff §4.4).

## `<head>` theme-color meta tags

Both tags render on every request, independent of the manifest's single static `theme_color`:

```html
<meta name="theme-color" media="(prefers-color-scheme: light)" content="#E6E1D6">
<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#1C1822">
```

Values are `--color-background` per theme (light/dark), not `--color-primary` — this is the
color actually adjacent to the status bar, per `design-system.md` §7.

## `/` redirect contract

```text
GET /  →  307 redirect  →  /recommend
```

No signed-out branch exists in this slice (no auth backend yet) — `/signin` is out of scope
until feature 002 ships. This is a documented assumption in `spec.md`, not a silent gap.

## Safe-area contract (per edge-docked element)

| Element | Inset expression |
|---|---|
| TabBar bottom padding | `env(safe-area-inset-bottom, 22px)` |
| BottomSheet bottom padding | `calc(30px + env(safe-area-inset-bottom))` |
| Sticky screen headers | `env(safe-area-inset-top)` — no floor, no `--wtw-proto-inset-top` |
| Toast (future, feature 007) | not built this slice — reserved `--z-toast` only |

`viewport-fit=cover` is set once in the root viewport export. Browser-tab mode must not add
extra inset padding beyond what the browser chrome already reserves — insets naturally
resolve to `0` there without any JS branch needed, per `design-system.md` §7's display-mode
matrix.

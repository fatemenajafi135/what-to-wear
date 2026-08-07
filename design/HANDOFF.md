# What to Wear: Design System

A component library for the What to Wear prototype, built as importable Design Components (`.dc.html`). This project's authoring model doesn't support a compiled CSS/JSX design-system package, so "centralized and reusable" here means: shared `.dc.html` files mounted with `<dc-import>`, all drawing from one token reference instead of duplicating inline styles per screen.

## Start here
1. **Design Tokens.dc.html** — the canonical color, type, spacing, radius and shadow reference every component below is built from. Never introduce a new hex/px value inline; extend the tokens page first, then update the components.
2. **Component Library.dc.html** — a live catalog of every component below with its variants rendered side by side, grouped the same way as this table (Buttons · Selection & status · Navigation · Overlays & media).

## Why this isn't a components/ folder tree
This authoring model mounts children with `<dc-import name="X">`, which only resolves a sibling `X.dc.html` in the same directory as the importer — no nested folder paths, no `.jsx`/`.d.ts`/`.prompt.md` triads, no compiled CSS package. So every reusable component here is a flat file at the project root; "Component Library.dc.html" is the catalog/index page that stands in for a `components.card.html`-style showcase, and this readme is the prop reference in place of per-component `.d.ts` files.

## Components

| File | Purpose | Key props |
|---|---|---|
| `Button.dc.html` | Primary CTA / secondary / outline button | `label`, `variant` (primary/secondary/outline), `fullWidth`, `disabled`, `onClick` |
| `IconButton.dc.html` | Circular icon-only button | `icon` (back/close/settings/dots/heart/heartFilled/filter/calendar/history/plus), `size`, `onClick` |
| `Chip.dc.html` | Selectable pill (category, filter, style, color) | `label`, `active`, `onClick` |
| `Badge.dc.html` | Small status/citation pill | `label`, `tone` (citation/status/muted/count) |
| `Switch.dc.html` | Toggle switch | `checked`, `onChange` |
| `SegmentedControl.dc.html` | 2–3 option tab switcher | `options`, `value`, `onChange` |
| `TopHeader.dc.html` | Screen header: back button + title/subtitle + optional right icon or pill | `title`, `subtitle`, `onBack`, `rightType`, `rightIcon`/`rightLabel`, `onRightAction` |
| `TabBar.dc.html` | Bottom navigation (Recommend/Closet/+/Outfits/Profile) | `activeKey`, `onNavigate`, `onAdd` |
| `BottomSheet.dc.html` | Modal action sheet with grouped rows | `open`, `title`, `subtitle`, `sections`, `onClose` |
| `AvatarInitial.dc.html` | Circular initial avatar | `personName`, `size` |

Usage pattern (all follow the same shape):
```html
<dc-import name="Button" label="Continue" variant="primary" on-click="{{ submit }}" hint-size="100%,46px"></dc-import>
```
kebab-case attributes become the child's camelCase props; `hint-size` is required on every mount.

## What's centralized vs. what stayed bespoke
- **Centralized:** every screen header, the bottom tab bar, all category/filter/style/color chips, citation and status badges, the profile avatar, the notifications switch, the item-menu and outfit-menu action sheets, and the main CTA buttons.
- **Left bespoke (by design, not oversight):** the "Add to Closet" sheet (icon + title + description rows, richer than BottomSheet's plain label rows) and the Outfits "Filter & sort" sheet (mixed sort-chip + filter-chip layout). Both would lose visual richness if forced into `BottomSheet`'s current shape; flag if you'd like `BottomSheet` extended to support custom row content instead.

## Extending the system
- New color/spacing value → add it to `Design Tokens.dc.html` first, then use the literal in the component.
- New shared UI pattern used 2+ times → pull it into its own `.dc.html` here rather than duplicating inline styles across screens.
- Every component that's meant to be embedded elsewhere should declare its props in `data-props` so it surfaces correctly in the Tweaks panel.

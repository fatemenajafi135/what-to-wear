# Contract: Shared component prop APIs

This is the interface contract other features build against. Getting a name wrong here is
paid seven more times (per the handoff) — treat changes to this file as breaking changes to
downstream features once 002+ starts consuming these components.

Conventions across every component below: no `theme` prop (see `data-model.md`); disabled is
always `disabled?: boolean` rendered as opacity 0.5 + inert, never a color prop; every
icon-only or sub-44px control gets the hit-area pseudo-element automatically, not via a prop.

## Button

```ts
interface ButtonProps {
  variant?: "primary" | "secondary" | "outline"; // default "primary"
  width?: "full" | "intrinsic" | "stretch";        // default "full"
  state?: "default" | "loading" | "error";         // default "default"
  errorLabel?: string;                              // default "Try again", used when state="error"
  disabled?: boolean;
  type?: "button" | "submit";
  onClick?: () => void;
  href?: string; // renders as a Next.js Link with the same visual treatment
  children: React.ReactNode; // label, 1-3 words per copy conventions
}
```

## IconButton

```ts
type IconKeyword =
  | "back" | "close" | "settings" | "dots" | "heart" | "heartFilled"
  | "filter" | "calendar" | "history" | "plus" | "thumbsUp" | "thumbsDown";

interface IconButtonProps {
  icon: IconKeyword;
  size?: 28 | 34 | 40 | 48; // default 34, visual size only — hit area is always 44px
  label?: string;            // overrides the per-icon aria-label default
  disabled?: boolean;
  onClick?: () => void;
  href?: string;              // renders as a Next.js Link with the same visual treatment
}
```

## Chip

```ts
interface ChipProps {
  active?: boolean;   // default false
  disabled?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}
```

## Badge

```ts
interface BadgeProps {
  tone: "citation" | "status" | "muted" | "count";
  children: React.ReactNode;
  // never interactive — no onClick, no href, ever
}
```

## Switch

```ts
interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  "aria-label"?: string; // required if no visible label wraps the Switch
}
```

## SegmentedControl

```ts
interface SegmentedOption { value: string; label: string; }

interface SegmentedControlProps {
  options: SegmentedOption[]; // 2-3 options
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean; // dims all options
}
```

## TopHeader

```ts
interface TopHeaderProps {
  title: string;      // becomes the screen's <h1>
  subtitle?: string;
  onBack?: () => void; // presence renders the back IconButton
  backHref?: string;    // renders the back IconButton as a Link instead
  rightSlot?:
    | { kind: "none" }
    | { kind: "icon"; icon: IconKeyword; onClick: () => void; label?: string }
    | { kind: "pill"; label: string; onClick: () => void }
    | { kind: "custom"; node: React.ReactNode }; // escape hatch for a self-contained
                                                   // interactive slot (e.g. a client
                                                   // component needing its own router access)
}
```

## TabBar

```ts
interface TabBarProps {
  destinations: NavDestination[]; // fixed 4 entries, see data-model.md
  activeId: NavId;
  createAction: { onClick: () => void }; // renders per-tier per design-system.md §5
  // TabBar itself renders all three tier markups (bar/rail/sidebar) as CSS-toggled
  // siblings — no `tier` prop; the breakpoint mechanism is CSS-only per Principle IX.
}
```

## BottomSheet

```ts
interface BottomSheetRow {
  label: string;
  tone?: "default" | "danger";
  onSelect: () => void;
  disabled?: boolean;
}

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  titleId: string;    // used for aria-labelledby on the underlying <dialog>
  title: string;
  state?: "normal" | "loading" | "error" | "empty";
  emptyLabel?: string;  // default "Nothing here yet"
  errorAction?: { label: string; onClick: () => void };
  rows?: BottomSheetRow[]; // grouped label-row variant only — bespoke sheets
                            // (Add to Closet, Filter & sort) are NOT this component,
                            // per design-system.md §3, and are out of scope for this slice.
}
```

## AvatarInitial

```ts
interface AvatarInitialProps {
  initial: string; // single uppercase character
  size?: 32 | 40 | 48 | 56 | 64 | 72; // default 40
}
```

## Banner

```ts
interface BannerProps {
  variant: "offline" | "error" | "info";
  children: React.ReactNode; // body copy
  action?: { label: string; onClick: () => void };
}
```

## Input

```ts
interface InputProps {
  type?: "text" | "email" | "password" | "number"; // default "text"
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;      // presence renders the error state + aria-invalid
  helpText?: string;   // mutually exclusive with error — error replaces it, never stacks
  disabled?: boolean;
  readOnly?: boolean;
  placeholder?: string;
  // type="password" auto-renders the show/hide IconButton per design-decisions.md §1.2
}
```

## Textarea

```ts
interface TextareaProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  helpText?: string;
  disabled?: boolean;
  placeholder?: string;
  // fixed min-height 94px, resize: vertical, per design-decisions.md §1.3
}
```

## Select

```ts
interface SelectOption { value: string; label: string; }

interface SelectProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  error?: string;
  disabled?: boolean;
  // native <select> — no custom listbox, per design-decisions.md §1.4
}
```

## DatePicker

```ts
interface DatePickerProps {
  label: string;
  value: string;    // ISO date string
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
  // native <input type="date">, display formatted via toLocaleDateString per §1.5
}
```

## TagInput

```ts
interface TagInputProps {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  // Enter commits current text as a chip; Backspace on empty field removes the last chip;
  // role="list" on the chip group, role="listitem" per chip, visually-hidden live region
  // announcing "{value} added" / "{value} removed" per design-decisions.md §1.6
}
```

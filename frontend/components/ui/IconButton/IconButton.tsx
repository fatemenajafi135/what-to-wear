import type { ButtonHTMLAttributes } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  X,
  Settings,
  Ellipsis,
  Heart,
  SlidersHorizontal,
  Calendar,
  History,
  Plus,
  ThumbsUp,
  Eye,
  EyeOff,
  SquarePen,
  type LucideIcon,
} from "lucide-react";
import styles from "./IconButton.module.css";

export type IconKeyword =
  | "back"
  | "close"
  | "settings"
  | "dots"
  | "heart"
  | "heartFilled"
  | "filter"
  | "calendar"
  | "history"
  | "plus"
  | "thumbsUp"
  | "thumbsDown"
  // Password show/hide toggle — docs/design-decisions.md §1.2, not part of
  // design-system.md §3's own keyword table but the same IconButton pattern.
  | "eye"
  | "eyeOff"
  // Recommend TopHeader's "New chat" action (design-system.md Screen anatomy
  // → Recommend, item 1) — feature 008.
  | "newChat";

const ICONS: Record<IconKeyword, LucideIcon> = {
  back: ArrowLeft,
  close: X,
  settings: Settings,
  dots: Ellipsis,
  heart: Heart,
  heartFilled: Heart,
  filter: SlidersHorizontal,
  calendar: Calendar,
  history: History,
  plus: Plus,
  thumbsUp: ThumbsUp,
  thumbsDown: ThumbsUp,
  eye: Eye,
  eyeOff: EyeOff,
  newChat: SquarePen,
};

const DEFAULT_LABELS: Record<IconKeyword, string> = {
  back: "Back",
  close: "Close",
  settings: "Settings",
  dots: "More options",
  heart: "Save",
  heartFilled: "Unsave",
  filter: "Filter",
  calendar: "Calendar",
  history: "Chat history",
  plus: "Add",
  thumbsUp: "Helpful",
  thumbsDown: "Not helpful",
  eye: "Show password",
  eyeOff: "Hide password",
  newChat: "New chat",
};

export interface IconButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  icon: IconKeyword;
  size?: 28 | 34 | 40 | 48;
  label?: string;
  /** Renders as a Next.js Link with the same visual treatment instead of a <button>. */
  href?: string;
}

/**
 * design/design-system.md §3 IconButton. Visual size 28-48px (default 34);
 * hit area is always the 44px pseudo-element regardless of the `size` prop.
 * `thumbsDown` reuses the thumbsUp glyph rotated 180° so the pair stays
 * visually paired, per the design system's own note.
 */
export function IconButton({
  icon,
  size = 34,
  label,
  className,
  disabled,
  type = "button",
  href,
  ...rest
}: IconButtonProps) {
  const Icon = ICONS[icon];
  const ariaLabel = label ?? DEFAULT_LABELS[icon];
  const isFilled = icon === "heartFilled";
  const isFlipped = icon === "thumbsDown";
  const strokeWidth = 2.1;
  const classes = ["control", "hitArea", styles.iconButton, className]
    .filter(Boolean)
    .join(" ");
  const glyph = (
    <Icon
      size={Math.round(size * 0.53)}
      strokeWidth={strokeWidth}
      fill={isFilled ? "currentColor" : "none"}
      style={isFlipped ? { transform: "rotate(180deg)" } : undefined}
      aria-hidden="true"
    />
  );

  if (href && !disabled) {
    return (
      <Link href={href} aria-label={ariaLabel} className={classes} style={{ width: size, height: size }}>
        {glyph}
      </Link>
    );
  }

  return (
    <button
      type={type}
      aria-label={ariaLabel}
      disabled={disabled}
      className={classes}
      style={{ width: size, height: size }}
      {...rest}
    >
      {glyph}
    </button>
  );
}

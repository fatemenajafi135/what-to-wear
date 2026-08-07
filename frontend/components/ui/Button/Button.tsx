import type { ButtonHTMLAttributes, ReactNode } from "react";
import Link from "next/link";
import styles from "./Button.module.css";

export interface ButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  variant?: "primary" | "secondary" | "outline";
  width?: "full" | "intrinsic" | "stretch";
  state?: "default" | "loading" | "error";
  errorLabel?: string;
  children: ReactNode;
  /** Renders as a Next.js Link with the same visual treatment instead of a <button>. */
  href?: string;
}

/**
 * design/design-system.md §3 Button. Loading replaces the button with a
 * skeleton-pulse block at the same footprint (not clickable); Error shows a
 * dedicated transparent/--color-error treatment with `errorLabel` in place
 * of the normal label. Disabled is always opacity 0.5 + pointer-events none
 * (docs/design-decisions.md §5) — never a dedicated color token.
 */
export function Button({
  variant = "primary",
  width = "full",
  state = "default",
  errorLabel = "Try again",
  className,
  disabled,
  type = "button",
  children,
  href,
  ...rest
}: ButtonProps) {
  if (state === "loading") {
    return (
      <div
        className={[styles.button, styles[width], styles.loadingSkeleton].join(" ")}
        aria-hidden="true"
      />
    );
  }

  const variantClass = state === "error" ? styles.error : styles[variant];
  const classes = ["control", styles.button, styles[width], variantClass, className]
    .filter(Boolean)
    .join(" ");
  const label = state === "error" ? errorLabel : children;

  if (href && !disabled) {
    return (
      <Link href={href} className={classes}>
        {label}
      </Link>
    );
  }

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled}
      {...rest}
    >
      {label}
    </button>
  );
}

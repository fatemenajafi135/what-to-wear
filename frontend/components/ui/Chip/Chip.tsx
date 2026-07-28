import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./Chip.module.css";

export interface ChipProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  active?: boolean;
  children: ReactNode;
}

/**
 * design/design-system.md §3 Chip. Selectable pill (category/filter/style/
 * color). Disabled renders non-interactive per the opacity convention
 * (docs/design-decisions.md §5) — no separate disabled color.
 */
export function Chip({ active = false, className, disabled, type = "button", children, ...rest }: ChipProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      aria-pressed={active}
      className={[styles.chip, active && styles.active, className].filter(Boolean).join(" ")}
      {...rest}
    >
      {children}
    </button>
  );
}

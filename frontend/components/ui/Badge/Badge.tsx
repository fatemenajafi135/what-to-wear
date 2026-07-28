import type { ReactNode } from "react";
import styles from "./Badge.module.css";

export interface BadgeProps {
  tone: "citation" | "status" | "muted" | "count";
  children: ReactNode;
}

/**
 * design/design-system.md §3 Badge. Non-interactive status pill — never
 * tappable, no states beyond tone.
 */
export function Badge({ tone, children }: BadgeProps) {
  return <span className={[styles.badge, styles[tone]].join(" ")}>{children}</span>;
}

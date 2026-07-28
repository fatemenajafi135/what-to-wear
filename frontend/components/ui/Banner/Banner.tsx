import type { ReactNode } from "react";
import styles from "./Banner.module.css";

export interface BannerProps {
  variant: "offline" | "error" | "info";
  children: ReactNode;
  action?: { label: string; onClick: () => void };
}

/**
 * design/design-system.md §3 Banner. Full-width inline strip.
 * role="status" aria-live="polite" per §7/§8's a11y requirements.
 */
export function Banner({ variant, children, action }: BannerProps) {
  return (
    <div className={[styles.banner, styles[variant]].join(" ")} role="status" aria-live="polite">
      <span className="textBody">{children}</span>
      {action && (
        <button type="button" className={styles.action} onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  );
}

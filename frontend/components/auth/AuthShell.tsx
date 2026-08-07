import type { ReactNode } from "react";
import styles from "./AuthShell.module.css";

interface AuthShellProps {
  children: ReactNode;
}

/**
 * Shared chrome for all four auth screens (design-system.md §5's content
 * width caps table: full-bleed max-width 360px mobile/tablet, gains a
 * `--color-surface` panel max-width 400px at desktop). No TopHeader exists
 * in the auth stack, so the wordmark is promoted to the screen's <h1> here
 * (handoff §5.1; constitution VIII requires exactly one <h1> per screen and
 * none of the four auth screens has another heading candidate).
 *
 * `role="main"` per design-system §8. `tabIndex={-1}` + `:focus-visible`
 * mirrors TopHeader's own <h1> pattern so FocusOnNavigate (reused in
 * app/(auth)/layout.tsx) can focus it without joining the tab order.
 */
export function AuthShell({ children }: AuthShellProps) {
  return (
    <div role="main" className={styles.main}>
      <div className={styles.panel}>
        {/* eslint-disable-next-line @next/next/no-img-element -- static SVG mark, no next/image optimization needed for a 32px inline glyph */}
        <img src="/mark.svg" alt="" width={32} height={32} className={styles.mark} />
        <h1 tabIndex={-1} className={`textDisplay ${styles.wordmark}`}>
          What to Wear
        </h1>
        {children}
      </div>
    </div>
  );
}

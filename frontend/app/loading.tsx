import styles from "./loading.module.css";

/**
 * Boot/splash pre-hydration state — docs/design-decisions.md §10:
 * "Not a route. It is the app-shell's pre-hydration state: centred mark.svg
 * at 32px on --color-background, wordmark in Display style, pulse gated by
 * prefers-reduced-motion. Belongs to feature 001." Implemented as Next.js's
 * `loading.tsx` Suspense-boundary convention — the idiomatic place for a
 * route-loading state, needing no bespoke splash-screen plumbing (research.md).
 */
export default function Loading() {
  return (
    <div className={styles.boot}>
      {/* eslint-disable-next-line @next/next/no-img-element -- static SVG mark, no next/image optimization needed for a 32px inline glyph */}
      <img src="/mark.svg" alt="" width={32} height={32} className={styles.mark} />
      <p className={`textDisplay ${styles.wordmark}`}>What to Wear</p>
    </div>
  );
}

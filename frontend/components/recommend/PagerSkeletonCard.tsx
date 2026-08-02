import styles from "./PagerSkeletonCard.module.css";

/**
 * design/design-system.md § Outfit suggestion pager, group-level states —
 * Loading: pulse blocks for title/meta, a description-shaped bar, and a
 * row of three 56×56 thumbnail placeholders. No arrows/indicator, since
 * the eventual card count isn't known yet. This is the group's own
 * loading treatment for a Start-styling call, replacing the plain
 * "Thinking…" caption (design system: "the multi-outfit generation's own
 * loading treatment is the pager's inline skeleton card, not this
 * trailing caption").
 */
export function PagerSkeletonCard() {
  return (
    <div className={styles.card} role="status" aria-label="Styling your outfit…">
      <div className={`skeleton ${styles.title}`} />
      <div className={`skeleton ${styles.description}`} />
      <div className={styles.thumbnails}>
        <div className={`skeleton ${styles.thumb}`} />
        <div className={`skeleton ${styles.thumb}`} />
        <div className={`skeleton ${styles.thumb}`} />
      </div>
    </div>
  );
}

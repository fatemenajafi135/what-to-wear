import { ClosetGrid } from "./ClosetGrid";
import styles from "./page.module.css";

/**
 * `/closet` — the list pane. At ≥1024px (design-system.md §5's two-pane
 * master-detail), it renders beside a placeholder detail pane; below that,
 * it's the whole screen and `/closet/:itemId` is reached by push navigation
 * (ClosetGrid's tiles are real `<Link>`s at every breakpoint).
 */
export default function ClosetPage() {
  return (
    <div className={styles.twoPane}>
      <div>
        <ClosetGrid />
      </div>
      <div className={styles.detailPane}>
        <p className="textBody">Select an item from your closet to see its details.</p>
      </div>
    </div>
  );
}

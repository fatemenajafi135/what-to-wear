import { OutfitsGrid } from "./OutfitsGrid";
import styles from "./page.module.css";

/**
 * `/outfits` — the list pane. At ≥1024px (design-system.md §5's two-pane
 * master-detail), it renders beside a placeholder detail pane; below that,
 * it's the whole screen and `/outfits/:outfitId` is reached by push
 * navigation (mirrors `/closet/page.tsx` exactly).
 */
export default function OutfitsPage() {
  return (
    <div className={styles.twoPane}>
      <div>
        <OutfitsGrid />
      </div>
      <div className={styles.detailPane}>
        <p className="textBody">Select an outfit to see its details.</p>
      </div>
    </div>
  );
}

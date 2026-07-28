import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { Button } from "@/components/ui/Button/Button";
import styles from "./page.module.css";

/**
 * Stub route — chrome + the closet.empty.first_run state from
 * design/design-system.md §6 (no real items exist in this slice).
 */
export default function ClosetPage() {
  return (
    <>
      <TopHeader title="Closet" subtitle="0 items" />
      <div className={styles.empty}>
        <p className={`textBody ${styles.body}`}>
          Your closet is empty. Add a few pieces and I&apos;ll start suggesting
          outfits.
        </p>
        <Button href="/add" width="intrinsic" className={styles.cta}>
          Add your first item
        </Button>
      </div>
    </>
  );
}

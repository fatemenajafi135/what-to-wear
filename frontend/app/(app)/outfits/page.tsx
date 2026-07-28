import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { Button } from "@/components/ui/Button/Button";
import styles from "./page.module.css";

/**
 * Stub route — chrome + the outfits.empty.first_run state from
 * design/design-system.md §6 (no real outfits exist in this slice).
 */
export default function OutfitsPage() {
  return (
    <>
      <TopHeader title="Outfits" subtitle="0 outfits" />
      <div className={styles.empty}>
        <p className={`textBody ${styles.body}`}>
          No outfits yet. Ask me to style something and I&apos;ll save the looks
          here.
        </p>
        <Button href="/recommend" width="intrinsic" className={styles.cta}>
          Go to Styling
        </Button>
      </div>
    </>
  );
}

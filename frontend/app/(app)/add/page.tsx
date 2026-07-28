import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { CloseAddOverlay } from "./CloseAddOverlay";
import styles from "./page.module.css";

/**
 * Stub route for the Create overlay launcher. The real upload → review-queue
 * flow (camera capture, scan-fill, bulk upload) is out of scope for this
 * slice (no real data/API calls) — this renders only the chrome and a
 * placeholder body.
 */
export default function AddItemPage() {
  return (
    <>
      <TopHeader title="Add item" rightSlot={{ kind: "custom", node: <CloseAddOverlay /> }} />
      <div className={styles.empty}>
        <p className={`textBody ${styles.body}`}>
          The photo-upload flow isn&apos;t wired up yet in this slice — this
          screen shows its chrome only.
        </p>
      </div>
    </>
  );
}

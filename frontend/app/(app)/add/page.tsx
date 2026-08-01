"use client";

import { useRouter } from "next/navigation";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { CloseAddOverlay } from "./CloseAddOverlay";
import { AddItemFlow } from "./AddItemFlow";
import styles from "./page.module.css";

/**
 * `/add` — the Create overlay's real body (feature 006), replacing 004's
 * chrome-only stub. Single-item flow only; the bulk-upload branch (§5.4)
 * is layered on top of this same page.
 *
 * design/design-system.md §5: stacked, one card at a time, centred at
 * max-width 480px from tablet up (`.content`).
 *
 * Closing after a successful save reuses `CloseAddOverlay`'s own
 * back-or-`/closet` fallback logic (docs/design-decisions.md §9) — both
 * paths (the header's X and a completed save) land the user the same
 * place a cold deep-link with no history would.
 */
export default function AddItemPage() {
  const router = useRouter();

  const handleSaved = () => {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push("/closet");
    }
  };

  return (
    <>
      <TopHeader title="Add item" rightSlot={{ kind: "custom", node: <CloseAddOverlay /> }} />
      <div className={styles.content}>
        <AddItemFlow onClose={handleSaved} />
      </div>
    </>
  );
}

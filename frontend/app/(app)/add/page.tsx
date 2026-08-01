"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { CloseAddOverlay } from "./CloseAddOverlay";
import { AddItemFlow } from "./AddItemFlow";
import { BulkChoiceSheet } from "./BulkChoiceSheet";
import { BulkQueue } from "./BulkQueue";
import styles from "./page.module.css";

const MAX_BULK_PHOTOS = 20; // research.md §6 addendum

type EntryState = { mode: "choice" } | { mode: "single" } | { mode: "bulk"; files: File[] };

/**
 * `/add` — the Create overlay's real body (feature 006), replacing 004's
 * chrome-only stub. Opens on the "Add to Closet" choice sheet
 * (design-system.md §3's named bespoke variant) — single item or bulk
 * (spec.md User Stories 1 and 2).
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
  const [entry, setEntry] = useState<EntryState>({ mode: "choice" });
  const bulkInputRef = useRef<HTMLInputElement>(null);

  const handleClose = () => {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push("/closet");
    }
  };

  const handleChooseBulk = () => {
    bulkInputRef.current?.click();
  };

  const handleBulkFilesSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).slice(0, MAX_BULK_PHOTOS);
    e.target.value = "";
    if (files.length > 0) {
      setEntry({ mode: "bulk", files });
    }
  };

  return (
    <>
      <TopHeader title="Add item" rightSlot={{ kind: "custom", node: <CloseAddOverlay /> }} />
      <div className={styles.content}>
        {entry.mode === "single" && <AddItemFlow onClose={handleClose} />}
        {entry.mode === "bulk" && <BulkQueue files={entry.files} onClose={handleClose} />}
      </div>

      <BulkChoiceSheet
        open={entry.mode === "choice"}
        onChooseSingle={() => setEntry({ mode: "single" })}
        onChooseBulk={handleChooseBulk}
        onClose={handleClose}
      />
      <input
        ref={bulkInputRef}
        type="file"
        accept="image/*"
        multiple
        className={styles.hiddenInput}
        aria-hidden="true"
        tabIndex={-1}
        onChange={handleBulkFilesSelected}
      />
    </>
  );
}

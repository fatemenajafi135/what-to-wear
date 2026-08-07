"use client";

import { useId } from "react";
import { Camera, Images } from "lucide-react";
import { addItemCopy } from "@/lib/add-item-copy";
import { useModalDialog } from "@/lib/useModalDialog";
import styles from "./BulkChoiceSheet.module.css";

export interface BulkChoiceSheetProps {
  open: boolean;
  onChooseSingle: () => void;
  onChooseBulk: () => void;
  onClose: () => void;
}

/**
 * design/design-system.md §3: "Bespoke variants not on this component...
 * the 'Add to Closet' sheet (icon+title+description rows) — custom markup
 * in the app shell, richer than BottomSheet's plain label rows." Copy:
 * `add_item.bulk.*` (design-system §6). The single-item row's own
 * title/subtitle aren't in the design's copy table (only the bulk option's
 * are) — the sheet's two-row shape implies one, so `addItemCopy.bulk.
 * singleOption*` fills that specific gap with matching tone, recorded here
 * rather than left silently invented in a copy table nobody can find.
 */
export function BulkChoiceSheet({ open, onChooseSingle, onChooseBulk, onClose }: BulkChoiceSheetProps) {
  const titleId = useId();
  // `onClose` here navigates away from /add, so firing it on a successful
  // choice was severe — see lib/useModalDialog.ts.
  const { dialogRef, onNativeClose } = useModalDialog(open, onClose);

  return (
    <dialog ref={dialogRef} className={styles.dialog} aria-labelledby={titleId} onClose={onNativeClose}>
      <div className={styles.content}>
        <h2 id={titleId} className={`textSectionTitle ${styles.title}`}>
          {addItemCopy.bulk.title}
        </h2>
        <p className={`textBody ${styles.subtitle}`}>{addItemCopy.bulk.subtitle}</p>

        <button type="button" className={`control ${styles.row}`} onClick={onChooseSingle}>
          <Camera size={22} strokeWidth={2} aria-hidden="true" className={styles.rowIcon} />
          <span className={styles.rowText}>
            <span className={styles.rowTitle}>{addItemCopy.bulk.singleOptionTitle}</span>
            <span className={styles.rowSubtitle}>{addItemCopy.bulk.singleOptionSubtitle}</span>
          </span>
        </button>

        <button type="button" className={`control ${styles.row}`} onClick={onChooseBulk}>
          <Images size={22} strokeWidth={2} aria-hidden="true" className={styles.rowIcon} />
          <span className={styles.rowText}>
            <span className={styles.rowTitle}>{addItemCopy.bulk.optionTitle}</span>
            <span className={styles.rowSubtitle}>{addItemCopy.bulk.optionSubtitle}</span>
          </span>
        </button>
      </div>
    </dialog>
  );
}

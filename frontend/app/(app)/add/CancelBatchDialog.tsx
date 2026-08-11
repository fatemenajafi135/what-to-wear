"use client";

import { useEffect, useId, useRef } from "react";
import { Button } from "@/components/ui/Button/Button";
import { useModalDialog } from "@/lib/useModalDialog";
import { addItemCopy } from "@/lib/add-item-copy";
import styles from "./CancelBatchDialog.module.css";

export interface CancelBatchDialogProps {
  open: boolean;
  savedCount: number;
  total: number;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * docs/design-decisions.md §64: canceling a bulk batch after at least one
 * item has already saved is the one case issue #62 identifies as risky —
 * the rest of the queue is abandoned with no warning otherwise. Reuses the
 * same bespoke `<dialog>` pattern §22.2 established for closet-item delete
 * and §40 reused for outfit delete (real `<dialog>` modal semantics,
 * focus trap/restore, safe-area-aware bottom padding) rather than a fresh
 * one — a third instance of an already-established pattern, not a new
 * component category.
 *
 * Copy is DRAFT, not design-owner-approved — see the comment on
 * `addItemCopy.cancelBatch`.
 */
export function CancelBatchDialog({ open, savedCount, total, onConfirm, onCancel }: CancelBatchDialogProps) {
  const triggerRef = useRef<Element | null>(null);
  const titleId = useId();

  useEffect(() => {
    if (open) triggerRef.current = document.activeElement;
  }, [open]);

  const handleClose = () => {
    if (triggerRef.current instanceof HTMLElement) {
      triggerRef.current.focus();
    }
    onCancel();
  };

  const { dialogRef, onNativeClose } = useModalDialog(open, handleClose);

  return (
    <dialog ref={dialogRef} className={styles.dialog} aria-labelledby={titleId} onClose={onNativeClose}>
      <div className={styles.content}>
        <h2 id={titleId} className={`textSectionTitle ${styles.title}`}>
          {addItemCopy.cancelBatch.title}
        </h2>
        <p className={`textBody ${styles.body}`}>{addItemCopy.cancelBatch.body(savedCount, total)}</p>
        <Button variant="outline" onClick={onConfirm} state="error" errorLabel={addItemCopy.cancelBatch.confirmCta}>
          {addItemCopy.cancelBatch.confirmCta}
        </Button>
        <button type="button" className={`control ${styles.cancelAction}`} onClick={handleClose}>
          {addItemCopy.cancelBatch.keepGoingCta}
        </button>
      </div>
    </dialog>
  );
}

"use client";

import { useEffect, useId, useRef } from "react";
import { Button } from "@/components/ui/Button/Button";
import { useModalDialog } from "@/lib/useModalDialog";
import styles from "./DeleteOutfitDialog.module.css";

export interface DeleteOutfitDialogProps {
  open: boolean;
  outfitTitle: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * docs/design-decisions.md §40: reuses `DeleteConfirmDialog.tsx`'s exact
 * bespoke pattern (title `Delete {title}?`, body `This can't be undone.`,
 * outline Cancel + danger-toned Delete, native `<dialog>`/`showModal()`
 * focus trap, explicit focus-restore on close) — every reason §22.2 gave
 * for confirming a closet-item delete applies identically to a saved
 * outfit, so this is the same call, not a fresh one.
 */
export function DeleteOutfitDialog({ open, outfitTitle, onConfirm, onCancel }: DeleteOutfitDialogProps) {
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
          Delete {outfitTitle}?
        </h2>
        <p className={`textBody ${styles.body}`}>This can&apos;t be undone.</p>
        <Button variant="outline" onClick={onConfirm} state="error" errorLabel="Delete">
          Delete
        </Button>
        <button type="button" className={`control ${styles.cancelAction}`} onClick={handleClose}>
          Cancel
        </button>
      </div>
    </dialog>
  );
}

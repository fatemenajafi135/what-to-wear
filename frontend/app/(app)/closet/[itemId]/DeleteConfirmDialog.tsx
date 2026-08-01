"use client";

import { useEffect, useId, useRef } from "react";
import { Button } from "@/components/ui/Button/Button";
import styles from "./DeleteConfirmDialog.module.css";

export interface DeleteConfirmDialogProps {
  open: boolean;
  itemName: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * docs/design-decisions.md §22.2: the design specifies no confirmation
 * before the overflow menu's danger-tone Delete row fires a hard,
 * unrecoverable delete — a real gap this closes with a bespoke `<dialog>`
 * card, the same escape hatch design-system.md §3 names ("richer than
 * BottomSheet's plain label rows") and `CalendarPrimer` already uses for
 * exactly this situation. Native `<dialog>` + `showModal()` gives a real
 * focus trap for free but not focus restoration on close, so the invoking
 * element is captured on open and refocused explicitly here — matching
 * `CalendarPrimer`'s own precedent.
 */
export function DeleteConfirmDialog({ open, itemName, onConfirm, onCancel }: DeleteConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<Element | null>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      triggerRef.current = document.activeElement;
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  const handleClose = () => {
    if (triggerRef.current instanceof HTMLElement) {
      triggerRef.current.focus();
    }
    onCancel();
  };

  return (
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      aria-labelledby={titleId}
      onClose={handleClose}
      onCancel={handleClose}
    >
      <div className={styles.content}>
        <h2 id={titleId} className={`textSectionTitle ${styles.title}`}>
          Delete {itemName}?
        </h2>
        <p className={`textBody ${styles.body}`}>This can&apos;t be undone.</p>
        {/* Button's `state="error"` is the design system's only token-backed
            "this is risky" treatment (transparent bg, --color-error
            border+text) — §3 Button documents `errorLabel` as exactly this,
            an override label shown in place of the normal one, so reusing
            it here for the destructive action isn't a semantic stretch. */}
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

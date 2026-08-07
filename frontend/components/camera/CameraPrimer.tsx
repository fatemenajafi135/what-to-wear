"use client";

import { useEffect, useId, useRef } from "react";
import { Button } from "@/components/ui/Button/Button";
import { cameraPrimerCopy } from "@/lib/add-item-copy";
import { useModalDialog } from "@/lib/useModalDialog";
import styles from "./CameraPrimer.module.css";

export interface CameraPrimerProps {
  open: boolean;
  onContinue: () => void;
  onDismiss: () => void;
}

/**
 * The one-time permission primer before the real camera capture
 * (known-gaps.md §-2, spec.md FR-009). A bespoke `<dialog>`-based card,
 * modeled directly on `components/calendar/CalendarPrimer.tsx` — same
 * escape hatch (design-system.md §3), same copy shape
 * (docs/design-decisions.md §23.6), same focus-trap/restore behavior.
 *
 * Unlike the calendar primer, declining here must not block the upload
 * flow entirely (spec.md SC-006) — the caller (`Dropzone`) is responsible
 * for opening the file input either way; this component only decides
 * *whether* `onContinue` (primed) or `onDismiss` (not primed, but still
 * proceeding) fires, per research.md §7's addendum.
 */
export function CameraPrimer({ open, onContinue, onDismiss }: CameraPrimerProps) {
  const triggerRef = useRef<Element | null>(null);
  const titleId = useId();


  useEffect(() => {
    if (open) triggerRef.current = document.activeElement;
  }, [open]);

  const restoreFocus = () => {
    if (triggerRef.current instanceof HTMLElement) {
      triggerRef.current.focus();
    }
  };

  const handleContinue = () => {
    restoreFocus();
    onContinue();
  };

  const handleDismiss = () => {
    restoreFocus();
    onDismiss();
  };

  const { dialogRef, onNativeClose } = useModalDialog(open, handleDismiss);

  return (
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      aria-labelledby={titleId}
      onClose={onNativeClose}
    >
      <div className={styles.content}>
        <h2 id={titleId} className={`textSectionTitle ${styles.title}`}>
          {cameraPrimerCopy.title}
        </h2>
        <p className={`textBody ${styles.body}`}>{cameraPrimerCopy.body}</p>
        <Button onClick={handleContinue}>{cameraPrimerCopy.continueCta}</Button>
        <button type="button" className={`control ${styles.notNow}`} onClick={handleDismiss}>
          {cameraPrimerCopy.notNowCta}
        </button>
      </div>
    </dialog>
  );
}

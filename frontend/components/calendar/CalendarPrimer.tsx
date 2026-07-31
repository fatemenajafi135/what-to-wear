"use client";

import { useEffect, useId, useRef } from "react";
import { Button } from "@/components/ui/Button/Button";
import styles from "./CalendarPrimer.module.css";

export interface CalendarPrimerProps {
  open: boolean;
  onContinue: () => void;
  onDismiss: () => void;
}

/**
 * The one-time permission primer before the real Google consent screen
 * (known-gaps.md §-2, spec.md FR-002). A bespoke `<dialog>`-based card,
 * not the `BottomSheet` component — `BottomSheet`'s API is label-only rows
 * with no slot for body text, and design-system.md §3 names exactly this
 * situation ("richer than BottomSheet's plain label rows") as the
 * documented escape hatch for a bespoke variant. Copy and rationale:
 * docs/design-decisions.md §18.
 *
 * Native `<dialog>` + `showModal()` gives a real focus trap for free, but
 * NOT focus restoration on close (a common misconception — the spec never
 * promises it) — design-system.md §8 requires both ("restore focus to the
 * invoking control on close"), so the invoking element is captured on open
 * and refocused explicitly here.
 */
export function CalendarPrimer({ open, onContinue, onDismiss }: CalendarPrimerProps) {
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
    onDismiss();
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
          Before you connect
        </h2>
        <p className={`textBody ${styles.body}`}>
          I&apos;ll be able to see your event titles, times and locations so I can suggest
          outfits for what&apos;s actually on your schedule. You can disconnect anytime from
          Settings.
        </p>
        <Button onClick={onContinue}>Continue to Google</Button>
        <button type="button" className={`control ${styles.notNow}`} onClick={handleClose}>
          Not now
        </button>
      </div>
    </dialog>
  );
}

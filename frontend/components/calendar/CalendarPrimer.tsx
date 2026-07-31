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
 */
export function CalendarPrimer({ open, onContinue, onDismiss }: CalendarPrimerProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      aria-labelledby={titleId}
      onClose={onDismiss}
      onCancel={onDismiss}
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
        <button type="button" className={`control ${styles.notNow}`} onClick={onDismiss}>
          Not now
        </button>
      </div>
    </dialog>
  );
}

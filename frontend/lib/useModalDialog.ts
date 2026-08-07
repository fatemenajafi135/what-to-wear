"use client";

import { useEffect, useRef } from "react";

/**
 * Shared plumbing for the app's native `<dialog>`-based overlays
 * (`BottomSheet`, the two permission primers, the delete confirmation, the
 * Add-to-Closet choice sheet). All five drive a modal dialog from an `open`
 * prop and want a callback when the USER dismisses it.
 *
 * The subtlety this exists for: `HTMLDialogElement.close()` dispatches a
 * `close` event, and the platform makes it indistinguishable from an
 * Escape-key dismissal. So the naive wiring — `onClose={onDismiss}` plus an
 * effect that calls `dialog.close()` when `open` goes false — fires the
 * dismissal callback on SUCCESS too, because succeeding is what sets `open`
 * to false.
 *
 * That shipped, and in `BulkChoiceSheet` it was severe: its dismissal
 * callback navigates away from /add, so choosing "Add bulk items" sent the
 * user to /closet the instant they picked their photos. The scan loop had
 * already started, so photos kept uploading from an unmounted screen — every
 * extract returned 200, no review card ever rendered, nothing was ever
 * saved, and no log showed anything wrong. The same latent defect was in the
 * other four: "Continue" on the camera primer also fired `onDismiss`, and
 * confirming a delete also fired `onCancel`.
 *
 * Introduced as shared code rather than copied a fifth time because the
 * constitution's Quality Bar asks for two concrete implementations or a
 * measured problem — this has five and one.
 *
 * Note it deliberately does NOT own focus restoration: three of the five
 * capture `document.activeElement` and restore it on their own action
 * handlers, which is theirs to sequence, not this hook's.
 */
export function useModalDialog(open: boolean, onDismiss: () => void) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closingProgrammatically = useRef(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      closingProgrammatically.current = true;
      dialog.close();
    }
  }, [open]);

  /** Wire to the dialog's `onClose` only. Escape fires `cancel` and THEN
   * `close`, so handling `close` alone covers dismissal exactly once —
   * wiring both, as these components used to, double-fired it. */
  const onNativeClose = () => {
    if (closingProgrammatically.current) {
      closingProgrammatically.current = false;
      return;
    }
    onDismiss();
  };

  return { dialogRef, onNativeClose };
}

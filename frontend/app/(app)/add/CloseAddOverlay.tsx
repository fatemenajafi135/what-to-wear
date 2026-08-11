"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { IconButton } from "@/components/ui/IconButton/IconButton";
import { CancelBatchDialog } from "./CancelBatchDialog";

export interface CloseAddOverlayProps {
  /**
   * issue #62 / docs/design-decisions.md §64: set only when closing now
   * would silently abandon a bulk batch that already has at least one item
   * saved — the specific risk the issue names. `null`/`undefined` (the
   * choice sheet, the single-item flow — nothing is saved before its final
   * Save tap — or a bulk batch with nothing saved yet) closes immediately,
   * preserving this component's original no-confirmation behaviour.
   */
  confirmation?: { savedCount: number; total: number } | null;
}

/**
 * docs/design-decisions.md §9: /add is not a persisted destination — closing
 * returns to the screen underneath when reached via in-app navigation, but a
 * cold deep-link (e.g. the manifest shortcut) has no history to return to,
 * so it falls back to /closet — "the screen its result lands in."
 */
export function CloseAddOverlay({ confirmation = null }: CloseAddOverlayProps = {}) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const handleClose = () => {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push("/closet");
    }
  };

  const handleClick = () => {
    if (confirmation) {
      setConfirmOpen(true);
    } else {
      handleClose();
    }
  };

  return (
    <>
      <IconButton icon="close" onClick={handleClick} />
      {confirmation && (
        <CancelBatchDialog
          open={confirmOpen}
          savedCount={confirmation.savedCount}
          total={confirmation.total}
          onConfirm={() => {
            setConfirmOpen(false);
            handleClose();
          }}
          onCancel={() => setConfirmOpen(false)}
        />
      )}
    </>
  );
}

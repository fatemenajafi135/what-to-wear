"use client";

import { useId } from "react";
import { useModalDialog } from "@/lib/useModalDialog";
import styles from "./BottomSheet.module.css";

export interface BottomSheetRow {
  label: string;
  tone?: "default" | "danger";
  onSelect: () => void;
  disabled?: boolean;
}

export interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  state?: "normal" | "loading" | "error" | "empty";
  emptyLabel?: string;
  errorAction?: { label: string; onClick: () => void };
  rows?: BottomSheetRow[];
}

/**
 * design/design-system.md §3 BottomSheet, with real dialog semantics per
 * the handoff's Trap 6 — native <dialog>/showModal() gives a modal focus
 * trap, Escape-to-close, and focus restore to the invoking element for
 * free, satisfying design-system.md §3's stated gap without a bespoke
 * focus-trap implementation. Motion (backdrop fade + panel translate/scale)
 * is reduced-motion gated in BottomSheet.module.css, per FR-011.
 */
export function BottomSheet({
  open,
  onClose,
  title,
  state = "normal",
  emptyLabel = "Nothing here yet",
  errorAction,
  rows = [],
}: BottomSheetProps) {
  const titleId = useId();

  const { dialogRef, onNativeClose } = useModalDialog(open, onClose);

  return (
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      aria-labelledby={titleId}
      onClose={onNativeClose}
    >
      <div className={styles.content}>
        <h2 id={titleId} className={`textSectionTitle ${styles.title}`}>
          {title}
        </h2>

        {state === "loading" && (
          <>
            <div className={styles.skeletonRow} style={{ width: "85%" }} />
            <div className={styles.skeletonRow} style={{ width: "65%" }} />
            <div className={styles.skeletonRow} style={{ width: "75%" }} />
          </>
        )}

        {state === "error" && (
          <p className={`textBody ${styles.emptyLabel}`}>
            {errorAction ? (
              <button type="button" onClick={errorAction.onClick} className="control">
                {errorAction.label}
              </button>
            ) : (
              "Something went wrong."
            )}
          </p>
        )}

        {state === "empty" && <p className={`textBody ${styles.emptyLabel}`}>{emptyLabel}</p>}

        {state === "normal" &&
          rows.map((row) => (
            <button
              key={row.label}
              type="button"
              className={[styles.row, row.tone === "danger" && styles.danger].filter(Boolean).join(" ")}
              onClick={row.onSelect}
              disabled={row.disabled}
            >
              {row.label}
            </button>
          ))}
      </div>
    </dialog>
  );
}

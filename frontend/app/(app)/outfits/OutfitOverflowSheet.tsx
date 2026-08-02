"use client";

import { BottomSheet, type BottomSheetRow } from "@/components/ui/BottomSheet/BottomSheet";

export interface OutfitOverflowSheetProps {
  open: boolean;
  onClose: () => void;
  isOnline: boolean;
  onLogWorn: () => void;
  onEditTitle: () => void;
  onDelete: () => void;
}

/**
 * design/design-system.md § 4.4 "The overflow sheet" — the same three rows
 * (Log as worn today / Edit title / Delete, Delete in `danger` tone) shared
 * by both the Outfits gallery card's "⋯" and Outfit detail's "⋯", mirroring
 * `ItemOverflowSheet.tsx`'s pattern exactly. No separate Favorite row here —
 * the heart is a direct control on both surfaces, not routed through this
 * menu (design-decisions.md's fix to spec.md FR-007, per /speckit-analyze).
 */
export function OutfitOverflowSheet({
  open,
  onClose,
  isOnline,
  onLogWorn,
  onEditTitle,
  onDelete,
}: OutfitOverflowSheetProps) {
  const fire = (action: () => void) => () => {
    onClose();
    action();
  };
  const rows: BottomSheetRow[] = [
    { label: "Log as worn today", onSelect: fire(onLogWorn), disabled: !isOnline },
    { label: "Edit title", onSelect: fire(onEditTitle), disabled: !isOnline },
    { label: "Delete", tone: "danger", onSelect: fire(onDelete), disabled: !isOnline },
  ];
  return <BottomSheet open={open} onClose={onClose} title="Outfit options" rows={rows} />;
}

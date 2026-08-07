"use client";

import { BottomSheet, type BottomSheetRow } from "@/components/ui/BottomSheet/BottomSheet";

export interface ItemOverflowSheetProps {
  open: boolean;
  onClose: () => void;
  isOnline: boolean;
  onEdit: () => void;
  onLogWorn: () => void;
  onToggleFavorite: () => void;
  onDelete: () => void;
}

/**
 * design/design-system.md §3 BottomSheet, § Screen anatomy → Item detail:
 * the overflow (⋯) menu 004 wired the trigger for but left empty. Four rows
 * in the design's fixed order: Edit, Log as worn today, Favorite, Delete
 * (danger tone). "Log as worn today" disables offline per FR-008 — nothing
 * is queued, so a disabled control is the only honest state (design-system
 * §6). Each row closes the sheet itself after firing its callback, matching
 * how a native action-sheet row behaves.
 */
export function ItemOverflowSheet({
  open,
  onClose,
  isOnline,
  onEdit,
  onLogWorn,
  onToggleFavorite,
  onDelete,
}: ItemOverflowSheetProps) {
  const fire = (action: () => void) => () => {
    onClose();
    action();
  };

  const rows: BottomSheetRow[] = [
    { label: "Edit", onSelect: fire(onEdit) },
    { label: "Log as worn today", onSelect: fire(onLogWorn), disabled: !isOnline },
    { label: "Favorite", onSelect: fire(onToggleFavorite) },
    { label: "Delete", tone: "danger", onSelect: fire(onDelete) },
  ];

  return <BottomSheet open={open} onClose={onClose} title="Item options" rows={rows} />;
}

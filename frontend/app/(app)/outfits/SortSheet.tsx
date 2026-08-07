"use client";

import { SlidersHorizontal } from "lucide-react";
import { BottomSheet, type BottomSheetRow } from "@/components/ui/BottomSheet/BottomSheet";
import styles from "./SortSheet.module.css";

// Mirrors backend/src/whattowear/repositories/supabase_outfits.py's `Sort`
// Literal exactly — the generated schema inlines it as a bare union on the
// query param rather than a named component, so there's no schema type to
// import here.
export type OutfitSort = "date" | "favorite" | "most_worn";

const SORT_LABELS: Record<OutfitSort, string> = {
  date: "Date added",
  favorite: "Favorited first",
  most_worn: "Most worn",
};

export interface SortSheetTriggerProps {
  onOpen: () => void;
}

/**
 * design/design-system.md § Outfits (gallery) item 1's "Filter & sort"
 * pill, and § BottomSheet's own note that this sheet is bespoke markup
 * ("mixed sort-chip/filter-chip layout ... richer than BottomSheet's plain
 * label rows"). This feature ships sort only — no filter facets, no
 * active-count badge, no "Clear" link — occasion/weather/formality
 * filtering is a deliberately deferred gap (design-decisions.md §41), not
 * built here. Uses the same Lucide `sliders-horizontal` glyph as
 * `IconButton`'s `filter` keyword — one filter icon across the app.
 */
export function SortSheetTrigger({ onOpen }: SortSheetTriggerProps) {
  return (
    <button type="button" className={`control ${styles.trigger}`} onClick={onOpen}>
      <SlidersHorizontal size={16} strokeWidth={2.1} aria-hidden="true" />
      Filter &amp; sort
    </button>
  );
}

export interface SortSheetProps {
  open: boolean;
  onClose: () => void;
  sort: OutfitSort;
  onChange: (sort: OutfitSort) => void;
}

export function SortSheet({ open, onClose, sort, onChange }: SortSheetProps) {
  const rows: BottomSheetRow[] = (Object.keys(SORT_LABELS) as OutfitSort[]).map((value) => ({
    label: sort === value ? `${SORT_LABELS[value]} (current)` : SORT_LABELS[value],
    onSelect: () => {
      onClose();
      onChange(value);
    },
  }));
  return <BottomSheet open={open} onClose={onClose} title="Sort outfits" rows={rows} />;
}

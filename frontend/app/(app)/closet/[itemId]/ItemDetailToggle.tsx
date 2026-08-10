"use client";

import { useState } from "react";
import { SegmentedControl } from "@/components/ui/SegmentedControl/SegmentedControl";

export type ItemDetailPhotoView = "isolated" | "original";

export interface ItemDetailToggleProps {
  value: ItemDetailPhotoView;
  onChange: (value: ItemDetailPhotoView) => void;
}

/**
 * Feature 018 (photo-to-items, spec.md FR-020, research.md §8): lets the
 * user flip between the isolated (background-removed) image and the
 * original, unmodified upload — the product's promise is "these are your
 * actual clothes," so the evidence stays reachable even when the isolated
 * version is what's shown by default. Rendered only when the item HAS an
 * isolated image (see `ItemDetailCard` — there's nothing to toggle to
 * otherwise); defaults to `"isolated"`.
 *
 * Uses the existing `SegmentedControl` (design-system.md §3) rather than a
 * bespoke control — a 2-option tab switcher is exactly what that component
 * already is. The labels below have no design-system table entry of their
 * own (this surface didn't exist when that table was written); flagged
 * DRAFT the same way `cameraPrimerCopy`/§63's detection-cap notice were
 * (docs/design-decisions.md §64), not invented silently (Principle VIII).
 */
export function ItemDetailToggle({ value, onChange }: ItemDetailToggleProps) {
  return (
    <SegmentedControl
      options={[
        { value: "isolated", label: "Isolated" },
        { value: "original", label: "Original" },
      ]}
      value={value}
      onChange={(next) => onChange(next as ItemDetailPhotoView)}
    />
  );
}

/** Convenience hook so `ItemDetailCard` doesn't need its own `useState`
 * boilerplate — kept in this file since the toggle is the only thing that
 * reads or writes this state. */
export function useItemDetailPhotoView(): [ItemDetailPhotoView, (value: ItemDetailPhotoView) => void] {
  const [view, setView] = useState<ItemDetailPhotoView>("isolated");
  return [view, setView];
}

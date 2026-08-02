"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

/**
 * The five Category chips the design system's Add-item and Closet screens
 * both specify. `full_body` has no chip of its own and lives under Bottoms —
 * the same mapping feature 004 resolved for the Closet filter, kept
 * identical here so a dress is filed the same way in both places.
 */
export const CATEGORY_CHIPS = [
  { group: "top", label: "Top" },
  { group: "bottom", label: "Bottom" },
  { group: "outerwear", label: "Outerwear" },
  { group: "footwear", label: "Footwear" },
  { group: "accessory", label: "Accessory" },
] as const;

export type CategoryChip = (typeof CATEGORY_CHIPS)[number]["group"];

/** Bottoms covers `full_body`, so its type list is the union of both. */
export function groupsForChip(chip: CategoryChip): string[] {
  return chip === "bottom" ? ["bottom", "full_body"] : [chip];
}

/** `necklace` -> `Necklace`, `bow_tie` -> `Bow tie`, `t-shirt` -> `T-shirt`. */
export function humanizeCategory(value: string): string {
  const spaced = value.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/**
 * `{group: [specific categories]}` from `GET /api/v1/taxonomy/categories`.
 *
 * Fetched rather than hard-coded: `categories.CATEGORY_GROUPS` is the single
 * source of truth and grows whenever new garment types show up in data. A
 * hand-mirrored copy of it would drift — this project already had one such
 * mirror (the colour palette, carrying a "keep in sync by hand" comment)
 * and deleted it once the review card stopped needing names at all
 * (constitution VII).
 *
 * Returns `{}` until it loads, and on failure — the Group control degrades
 * to free text, which is exactly what `category` is on the backend anyway,
 * so a taxonomy fetch failing never blocks adding an item.
 */
export function useCategoryTaxonomy(): Record<string, string[]> {
  const [taxonomy, setTaxonomy] = useState<Record<string, string[]>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await apiClient.GET("/api/v1/taxonomy/categories", {});
        if (!cancelled && data) setTaxonomy(data as Record<string, string[]>);
      } catch {
        // Left empty — see the docstring: the Group field still works.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return taxonomy;
}

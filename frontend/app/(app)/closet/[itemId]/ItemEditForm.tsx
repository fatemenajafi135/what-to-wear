"use client";

import { useState } from "react";
import { Chip } from "@/components/ui/Chip/Chip";
import { Input } from "@/components/ui/Input/Input";
import { Textarea } from "@/components/ui/Textarea/Textarea";
import { Button } from "@/components/ui/Button/Button";
import { apiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import styles from "./ItemEditForm.module.css";

type ClosetItemView = components["schemas"]["ClosetItemView"];

const CATEGORY_CHIPS: { value: string; label: string }[] = [
  { value: "top", label: "Top" },
  { value: "bottom", label: "Bottom" },
  { value: "outerwear", label: "Outerwear" },
  { value: "footwear", label: "Footwear" },
  { value: "accessory", label: "Accessory" },
];

export interface ItemEditFormProps {
  item: ClosetItemView;
  isOnline: boolean;
  onSaved: (item: ClosetItemView) => void;
}

/**
 * design/design-system.md § Screen anatomy → Item detail: "Edit swaps the
 * read-only card for an editable form (same field order, Chips for
 * Category, text inputs for the rest) ending in a full-width 'Save
 * changes' button." Field order matches `ItemDetailCard` exactly, down to
 * its "Category"/"Group" label inversion (specs/005-closet-write/
 * research.md §4): both write the same `category` column, Category-chips
 * setting it to a bare group name, Group's text input free-text override
 * of the same draft value — whichever the user touches last wins.
 */
export function ItemEditForm({ item, isOnline, onSaved }: ItemEditFormProps) {
  const [name, setName] = useState(item.name ?? "");
  const [category, setCategory] = useState(item.category);
  // Which Category chip reads as active. Separate from `category` (the
  // Group input's value, e.g. "blazer") because the chip set is the
  // coarser group — `item.category_group` is already server-computed
  // (categories.group_of), so this reads it directly rather than
  // duplicating that taxonomy client-side (constitution VI). A chip click
  // updates both this and `category` together; typing in Group only
  // updates `category`, leaving the chip's highlight as whichever group
  // was last explicitly chosen.
  const [categoryChip, setCategoryChip] = useState<string>(item.category_group);
  const [fabric, setFabric] = useState(item.fabric ?? "");
  const [colorsText, setColorsText] = useState(item.color_names.join(", "));
  const [notes, setNotes] = useState(item.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      // Only the fields the user actually touched are sent — critical for
      // Colour especially: `color_names` is a *nearest*-match display name
      // (colors.nearest_names), not necessarily the exact original hex, so
      // resending it unconditionally on every save would silently drift an
      // untouched item's stored color toward the nearest palette entry.
      const body: Record<string, string> = {};
      if (name !== (item.name ?? "")) body.name = name;
      if (category !== item.category) body.category = category;
      if (fabric !== (item.fabric ?? "")) body.fabric = fabric;
      if (colorsText !== item.color_names.join(", ")) body.colors_text = colorsText;
      if (notes !== (item.notes ?? "")) body.notes = notes;

      const { data, error: apiError } = await apiClient.PATCH("/api/v1/closet/items/{item_id}", {
        params: { path: { item_id: item.id } },
        body,
      });
      if (apiError || !data) {
        setError("Couldn't save your changes. Try again.");
        return;
      }
      onSaved(data);
    } catch {
      setError("Couldn't save your changes. Try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <Input label="Name" value={name} onChange={setName} />

      <div className={styles.field}>
        <span className={`textLabel ${styles.chipGroupLabel}`}>Category</span>
        <div className={styles.chipGroup} role="group" aria-label="Category">
          {CATEGORY_CHIPS.map((chip) => (
            <Chip
              key={chip.value}
              active={categoryChip === chip.value}
              onClick={() => {
                setCategoryChip(chip.value);
                setCategory(chip.value);
              }}
            >
              {chip.label}
            </Chip>
          ))}
        </div>
      </div>

      <Input label="Group" value={category} onChange={setCategory} />
      <Input label="Fabric" value={fabric} onChange={setFabric} />
      <Input label="Colour" value={colorsText} onChange={setColorsText} helpText="Separate multiple colours with commas" />
      <Textarea label="Notes" value={notes} onChange={setNotes} />

      {error && (
        <p className={`textCaption ${styles.errorText}`} role="alert">
          {error}
        </p>
      )}

      <Button type="submit" disabled={!isOnline || saving} state={saving ? "loading" : "default"}>
        Save changes
      </Button>
    </form>
  );
}

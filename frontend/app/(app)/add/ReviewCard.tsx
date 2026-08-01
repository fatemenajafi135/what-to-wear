"use client";

import { useRef, useState } from "react";
import { Chip } from "@/components/ui/Chip/Chip";
import { Input } from "@/components/ui/Input/Input";
import { Textarea } from "@/components/ui/Textarea/Textarea";
import { Button } from "@/components/ui/Button/Button";
import { isRecognizedColorName } from "@/lib/colors/validateColorName";
import { addItemCopy } from "@/lib/add-item-copy";
import styles from "./ReviewCard.module.css";

const CATEGORY_CHIPS: { value: string; label: string }[] = [
  { value: "top", label: "Top" },
  { value: "bottom", label: "Bottom" },
  { value: "outerwear", label: "Outerwear" },
  { value: "footwear", label: "Footwear" },
  { value: "accessory", label: "Accessory" },
];

export interface ReviewCardFields {
  name: string;
  category: string;
  fabric: string;
  color: string;
  notes: string;
}

export interface ReviewCardProps {
  photoUrl: string;
  /** Scan-derived starting values — every field editable regardless of
   * whether the scan found it (spec.md FR-003/FR-016: a blank review card
   * for "no garment found"/"Enter manually" is just this with empty
   * initial values, not a distinct form). */
  initial: Partial<ReviewCardFields>;
  saveLabel: string;
  onSave: (fields: ReviewCardFields) => Promise<void>;
  /** Set by the caller when a previous save attempt failed — renders the
   * Save button in its Error treatment (research.md §6). */
  saveError?: boolean;
}

/**
 * design/design-system.md § Add item "Review card fields": Name, Category
 * (chips), Group, Fabric, Color, Notes — the six fields, every one
 * scan-auto-filled where the scan found a value and manually editable
 * regardless (spec.md FR-005). Used for both the single-item flow and
 * each card in a bulk queue (`saveLabel` differs: "Save to Closet" vs
 * "Save & next").
 */
export function ReviewCard({ photoUrl, initial, saveLabel, onSave, saveError = false }: ReviewCardProps) {
  const [name, setName] = useState(initial.name ?? "");
  const [category, setCategory] = useState(initial.category ?? "");
  const [categoryChip, setCategoryChip] = useState(initial.category ?? "");
  const [fabric, setFabric] = useState(initial.fabric ?? "");
  const [color, setColor] = useState(initial.color ?? "");
  const [notes, setNotes] = useState(initial.notes ?? "");
  const [colorError, setColorError] = useState<string | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const colorFieldRef = useRef<HTMLDivElement>(null);

  /** Colour is the only field that can block a save, and it sits low in a
   * form whose submit button is lower still — so on a phone the button can
   * be tapped with the error rendered off-screen, which reads as "nothing
   * happened". Moving focus scrolls it into view and announces it. Focusing
   * through a wrapper rather than adding a ref to the shared `Input`: that
   * primitive is used across every form in the app and this is not a good
   * enough reason to change its contract. */
  const failColorValidation = (message: string) => {
    setColorError(message);
    colorFieldRef.current?.querySelector("input")?.focus();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // `colors` has no safe default at the backend (data-model.md §3) — an
    // item with no color at all isn't meaningfully saveable, unlike the
    // five attributes research.md §4 defaults instead.
    if (!color.trim()) {
      failColorValidation(addItemCopy.color.required);
      return;
    }
    if (!isRecognizedColorName(color)) {
      failColorValidation(addItemCopy.color.notRecognized);
      return;
    }
    setColorError(undefined);
    setSaving(true);
    try {
      await onSave({ name, category, fabric, color, notes });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className={styles.card} onSubmit={handleSubmit}>
      {/* design-system.md § Image treatment: review-card photo, 150px, 16px radius. */}
      {/* eslint-disable-next-line @next/next/no-img-element -- local object URL preview, not an optimizable remote asset */}
      <img src={photoUrl} alt="" className={styles.photo} />

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
      <div ref={colorFieldRef}>
        <Input
          label="Color"
          value={color}
          onChange={(v) => {
            setColor(v);
            if (colorError) setColorError(undefined);
          }}
          error={colorError}
          helpText="Needed so I can match this piece — e.g. navy, charcoal, olive."
        />
      </div>
      <Textarea label="Notes" value={notes} onChange={setNotes} />

      <Button type="submit" state={saveError ? "error" : saving ? "loading" : "default"} width="stretch">
        {saveLabel}
      </Button>
    </form>
  );
}

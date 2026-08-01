"use client";

import { useRef, useState } from "react";
import { Chip } from "@/components/ui/Chip/Chip";
import { Input } from "@/components/ui/Input/Input";
import { Textarea } from "@/components/ui/Textarea/Textarea";
import { Button } from "@/components/ui/Button/Button";
import { ColorField, isHex } from "./ColorField";
import { addItemCopy } from "@/lib/add-item-copy";
import styles from "./ReviewCard.module.css";

const CATEGORY_CHIPS: { value: string; label: string }[] = [
  { value: "top", label: "Top" },
  { value: "bottom", label: "Bottom" },
  { value: "outerwear", label: "Outerwear" },
  { value: "footwear", label: "Footwear" },
  { value: "accessory", label: "Accessory" },
];

/** Chip groups, not `Select`s. A native dropdown is a poor control on a
 * phone — it hides every option behind a tap and an OS sheet, for two
 * fields the scan usually pre-answers and the user is only verifying. It
 * also had a hazard of its own: a `<select>` whose value matches no option
 * silently selects its FIRST, so an undetected formality displayed (and
 * would have saved) as "casual". A chip group shows nothing selected, which
 * is the truth. Same treatment as Category and Season, so all four
 * taxonomy fields on this card behave identically. */
const FORMALITY_CHIPS = [
  { value: "casual", label: "Casual" },
  { value: "smart_casual", label: "Smart casual" },
  { value: "business_casual", label: "Business casual" },
  { value: "semi_formal", label: "Semi formal" },
  { value: "formal", label: "Formal" },
  { value: "black_tie", label: "Black tie" },
];

/** 0–5 per the frozen taxonomy (`warmth smallint check between 0 and 5`).
 * Worded, because the bare digits mean nothing to a person; the number is
 * what gets stored and is kept in the accessible name. */
const WARMTH_CHIPS = [
  { value: "0", label: "Airy" },
  { value: "1", label: "Light" },
  { value: "2", label: "Mild" },
  { value: "3", label: "Medium" },
  { value: "4", label: "Warm" },
  { value: "5", label: "Heaviest" },
];

const SEASON_CHIPS = ["spring", "summer", "autumn", "winter"] as const;
type Season = (typeof SEASON_CHIPS)[number];

export interface ReviewCardFields {
  name: string;
  category: string;
  /** Always `#rrggbb`, lowercased. */
  colors: string[];
  formality: string;
  warmth: string;
  season: Season[];
  fabric: string;
  pattern: string;
  fit: string;
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
 * The Add-item review card. Carries **every attribute the extractor
 * produces**, which is the whole point of scanning a photo:
 * category, colors, fabric, warmth, formality, season, pattern, fit — plus
 * Name, Group and Notes.
 *
 * It did not always. The first version showed the six fields
 * design-system.md's Add-item table lists (Name, Category, Group, Fabric,
 * Color, Notes) and sent only those, so `formality`, `warmth`, `season`,
 * `pattern` and `fit` were extracted by the VLM and then **thrown away** on
 * save — the backend filled defaults instead. Four photos of visibly
 * different garments all landed as `formality='casual', warmth=3,
 * season=[all four], pattern=null, fit=null`. The legacy app's
 * ExtractedItemForm carried all eight and guaranteed "100% of saved items
 * populated, none blank" (its SC-003); this restores that. Deliberate
 * deviation from the design's six-field table, recorded in
 * docs/design-decisions.md §30.
 *
 * Colour is hex and is SHOWN as colour — see `ColorField`. It was briefly a
 * name-only text field, which both destroyed the detected value (hex →
 * nearest palette name → that name's canonical hex) and told the user
 * nothing: "navy" does not say which navy the scan read.
 */
export function ReviewCard({
  photoUrl,
  initial,
  saveLabel,
  onSave,
  saveError = false,
}: ReviewCardProps) {
  const [name, setName] = useState(initial.name ?? "");
  const [category, setCategory] = useState(initial.category ?? "");
  const [categoryChip, setCategoryChip] = useState(initial.category ?? "");
  const [fabric, setFabric] = useState(initial.fabric ?? "");
  const [formality, setFormality] = useState(initial.formality ?? "");
  const [warmth, setWarmth] = useState(initial.warmth ?? "");
  const [season, setSeason] = useState<Season[]>(initial.season ?? []);
  const [pattern, setPattern] = useState(initial.pattern ?? "");
  const [fit, setFit] = useState(initial.fit ?? "");
  const [notes, setNotes] = useState(initial.notes ?? "");

  const [colors, setColors] = useState<string[]>(initial.colors ?? []);

  const [error, setError] = useState<string | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const colorFieldRef = useRef<HTMLDivElement>(null);

  const toggleSeason = (value: Season) =>
    setSeason((prev) => (prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value]));

  /** Colour is the only field whose control sits well above the submit
   * button, so on a phone the button can be tapped with its error rendered
   * off-screen — which reads as "the button does nothing".
   *
   * Falls back to the first focusable control in the field rather than
   * assuming an input exists: with no colours added yet there are no rows,
   * and the only thing to move to is the "Add color" button — which is
   * precisely the state that triggers the "required" error. */
  const failColor = (message: string) => {
    setError(message);
    const field = colorFieldRef.current;
    if (!field) return;
    const hexInputs = [...field.querySelectorAll<HTMLInputElement>('input[type="text"]')];
    // The offending row, not merely the first one — with several colours the
    // error is meaningless if focus lands on a valid entry. Falls back to
    // "Add color" when there are no rows at all, which is the state that
    // raises the "required" error.
    const target = hexInputs.find((input) => !isHex(input.value)) ?? hexInputs[0] ?? field.querySelector("button");
    (target as HTMLElement | null)?.focus();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (colors.length === 0) {
      failColor(addItemCopy.color.required);
      return;
    }
    if (colors.some((c) => !isHex(c))) {
      failColor(addItemCopy.color.notHex);
      return;
    }
    // The legacy form's SC-003 guarantee: an item saved through the scan
    // flow has every attribute populated, none blank. The scan fills these
    // in almost every case, so this fires only when it genuinely failed.
    const missing = !category.trim() || !formality || warmth === "" || season.length === 0;
    if (missing) {
      setError(addItemCopy.incomplete);
      return;
    }
    setError(undefined);
    setSaving(true);
    try {
      await onSave({
        name,
        category,
        colors: colors.map((c) => c.trim().toLowerCase()),
        formality,
        warmth: String(warmth),
        season,
        fabric,
        pattern,
        fit,
        notes,
      });
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
        <ColorField
          values={colors}
          onChange={(next) => {
            setColors(next);
            if (error) setError(undefined);
          }}
        />
      </div>

      <div className={styles.field}>
        <span className={`textLabel ${styles.chipGroupLabel}`}>Formality</span>
        <div className={styles.chipGroup} role="group" aria-label="Formality">
          {FORMALITY_CHIPS.map((chip) => (
            <Chip key={chip.value} active={formality === chip.value} onClick={() => setFormality(chip.value)}>
              {chip.label}
            </Chip>
          ))}
        </div>
      </div>

      <div className={styles.field}>
        <span className={`textLabel ${styles.chipGroupLabel}`}>Warmth</span>
        <div className={styles.chipGroup} role="group" aria-label="Warmth">
          {WARMTH_CHIPS.map((chip) => (
            <Chip
              key={chip.value}
              active={String(warmth) === chip.value}
              onClick={() => setWarmth(chip.value)}
              aria-label={`Warmth ${chip.value} — ${chip.label}`}
            >
              {chip.label}
            </Chip>
          ))}
        </div>
      </div>

      <div className={styles.field}>
        <span className={`textLabel ${styles.chipGroupLabel}`}>Season</span>
        <div className={styles.chipGroup} role="group" aria-label="Season">
          {SEASON_CHIPS.map((value) => (
            <Chip key={value} active={season.includes(value)} onClick={() => toggleSeason(value)}>
              {value[0]?.toUpperCase()}
              {value.slice(1)}
            </Chip>
          ))}
        </div>
      </div>

      <Input label="Pattern" value={pattern} onChange={setPattern} />
      <Input label="Fit" value={fit} onChange={setFit} />
      <Textarea label="Notes" value={notes} onChange={setNotes} />

      {error && (
        <p className={`textBody ${styles.formError}`} role="alert">
          {error}
        </p>
      )}

      <Button type="submit" state={saveError ? "error" : saving ? "loading" : "default"} width="stretch">
        {saveLabel}
      </Button>
    </form>
  );
}

"use client";

import { useRef, useState } from "react";
import { Chip } from "@/components/ui/Chip/Chip";
import { Input } from "@/components/ui/Input/Input";
import { Select } from "@/components/ui/Select/Select";
import { TagInput } from "@/components/ui/TagInput/TagInput";
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

/** Leading empty option on both Selects: a native <select> whose value
 * matches no option falls back to the FIRST one, so without this an
 * undetected formality would silently display (and save) as "casual" —
 * the same class of invented value this whole change removes. */
const NOT_DETECTED = { value: "", label: "Not detected — pick one" };

const FORMALITY_OPTIONS = [
  NOT_DETECTED,
  { value: "casual", label: "Casual" },
  { value: "smart_casual", label: "Smart casual" },
  { value: "business_casual", label: "Business casual" },
  { value: "semi_formal", label: "Semi formal" },
  { value: "formal", label: "Formal" },
  { value: "black_tie", label: "Black tie" },
];

/** 0–5 per the frozen taxonomy (`warmth smallint check between 0 and 5`).
 * Labelled rather than bare numerals — the scale is meaningless as digits. */
const WARMTH_OPTIONS = [
  NOT_DETECTED,
  { value: "0", label: "0 — airy" },
  { value: "1", label: "1 — light" },
  { value: "2", label: "2 — mild" },
  { value: "3", label: "3 — medium" },
  { value: "4", label: "4 — warm" },
  { value: "5", label: "5 — heaviest" },
];

const SEASON_CHIPS = ["spring", "summer", "autumn", "winter"] as const;
type Season = (typeof SEASON_CHIPS)[number];

export interface ReviewCardFields {
  name: string;
  category: string;
  /** Hex where the scan detected it, otherwise whatever the user typed —
   * the backend resolves a name to hex and passes a hex through unchanged. */
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
  /** Display names for `initial.colors`, positionally aligned. The card
   * shows these (a human can read "navy"; nobody reads "#1b2a4a") while
   * `initial.colors` keeps the exact hex the VLM detected — see the colour
   * note in the component docstring. */
  initialColorNames?: string[];
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
 * Colour is hex, not a name. `colors.py`'s docstring is explicit that hex
 * is the source of truth and names are derived, and the extractor returns
 * hex. Showing a name but SENDING one meant hex → nearest name → the
 * palette's canonical hex, so a detected `#22345d` was stored as navy's
 * `#1b2a4a`, and a multi-colour garment collapsed to one. Here the field
 * displays names and remembers the hex behind each: a chip the user did not
 * touch is sent as its original hex, and anything they type is sent as
 * typed for the backend to resolve.
 */
export function ReviewCard({
  photoUrl,
  initial,
  initialColorNames = [],
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

  // Display names, with the detected hex remembered per name so an untouched
  // chip round-trips exactly.
  const hexByName = useRef<Map<string, string>>(
    new Map((initial.colors ?? []).map((hex, i) => [initialColorNames[i] ?? hex, hex]))
  );
  const [colorTags, setColorTags] = useState<string[]>(
    (initial.colors ?? []).map((hex, i) => initialColorNames[i] ?? hex)
  );

  const [error, setError] = useState<string | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const colorFieldRef = useRef<HTMLDivElement>(null);

  const toggleSeason = (value: Season) =>
    setSeason((prev) => (prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value]));

  /** Colour is the only field whose control sits well above the submit
   * button, so on a phone the button can be tapped with its error rendered
   * off-screen — which reads as "the button does nothing". */
  const failColor = (message: string) => {
    setError(message);
    colorFieldRef.current?.querySelector("input")?.focus();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (colorTags.length === 0) {
      failColor(addItemCopy.color.required);
      return;
    }
    const unknown = colorTags.find((tag) => !hexByName.current.has(tag) && !isRecognizedColorName(tag));
    if (unknown) {
      failColor(addItemCopy.color.notRecognized);
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
        colors: colorTags.map((tag) => hexByName.current.get(tag) ?? tag),
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
        <TagInput
          label="Color"
          values={colorTags}
          onChange={(next) => {
            setColorTags(next);
            if (error) setError(undefined);
          }}
          placeholder="navy, charcoal…"
        />
      </div>

      <Select label="Formality" value={formality} onChange={setFormality} options={FORMALITY_OPTIONS} />
      <Select label="Warmth" value={String(warmth)} onChange={setWarmth} options={WARMTH_OPTIONS} />

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

"use client";

import { useState } from "react";
import { CATEGORY_GROUPS, FORMALITY_VALUES, SEASON_VALUES, type Formality, type Season } from "@/lib/taxonomy";
import type { CreateWardrobeItemFromUploadRequest, ExtractedAttributes } from "@/lib/types";

export interface ExtractedItemFormValue {
  category: string;
  colors: string[];
  formality: Formality | "";
  warmth: number | "";
  season: Season[];
  fabric: string;
  pattern: string;
  fit: string;
}

export function draftFromExtracted(extracted: ExtractedAttributes): ExtractedItemFormValue {
  return {
    category: extracted.category ?? "",
    colors: extracted.colors && extracted.colors.length > 0 ? extracted.colors : ["#000000"],
    formality: extracted.formality ?? "",
    warmth: extracted.warmth ?? "",
    season: extracted.season ?? [],
    fabric: extracted.fabric ?? "",
    pattern: extracted.pattern ?? "",
    fit: extracted.fit ?? "",
  };
}

function isComplete(v: ExtractedItemFormValue): boolean {
  return (
    v.category !== "" &&
    v.colors.length > 0 &&
    v.formality !== "" &&
    v.warmth !== "" &&
    v.season.length > 0 &&
    // SC-003: 100% of saved items populated, none blank -- enforced here
    // client-side (UX guard) and again by the backend 422 (source of truth).
    v.fabric.trim() !== "" &&
    v.pattern.trim() !== "" &&
    v.fit.trim() !== ""
  );
}

export function ExtractedItemForm({
  photoPath,
  initial,
  extractionOk,
  onSave,
  saving,
}: {
  photoPath: string;
  initial: ExtractedItemFormValue;
  extractionOk: boolean;
  onSave: (payload: CreateWardrobeItemFromUploadRequest) => void;
  saving: boolean;
}) {
  const [value, setValue] = useState<ExtractedItemFormValue>(initial);

  function update<K extends keyof ExtractedItemFormValue>(key: K, next: ExtractedItemFormValue[K]) {
    setValue((v) => ({ ...v, [key]: next }));
  }

  function toggleSeason(season: Season) {
    setValue((v) => ({
      ...v,
      season: v.season.includes(season) ? v.season.filter((s) => s !== season) : [...v.season, season],
    }));
  }

  function updateColor(index: number, hex: string) {
    setValue((v) => ({ ...v, colors: v.colors.map((c, i) => (i === index ? hex : c)) }));
  }

  function addColor() {
    setValue((v) => ({ ...v, colors: [...v.colors, "#000000"] }));
  }

  function removeColor(index: number) {
    setValue((v) => ({ ...v, colors: v.colors.filter((_, i) => i !== index) }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isComplete(value)) return;
    onSave({
      photo_path: photoPath,
      category: value.category,
      colors: value.colors,
      formality: value.formality as Formality,
      warmth: value.warmth as number,
      season: value.season,
      fabric: value.fabric.trim(),
      pattern: value.pattern.trim(),
      fit: value.fit.trim(),
    });
  }

  return (
    <form className="extracted-item-form" onSubmit={handleSubmit}>
      {!extractionOk && (
        <p className="extraction-warning">
          Couldn&apos;t confidently read this photo — fill in (or correct) the details below.
        </p>
      )}

      <label>
        Category
        <select value={value.category} onChange={(e) => update("category", e.target.value)} required>
          <option value="" disabled>
            Select a category
          </option>
          {CATEGORY_GROUPS.map((c) => (
            <option key={c} value={c}>
              {c.replace("_", " ")}
            </option>
          ))}
        </select>
      </label>

      <fieldset>
        <legend>Colors</legend>
        {value.colors.map((hex, i) => (
          <div key={i} className="color-row">
            <input type="color" value={hex} onChange={(e) => updateColor(i, e.target.value)} />
            <span>{hex}</span>
            {value.colors.length > 1 && (
              <button type="button" onClick={() => removeColor(i)}>
                Remove
              </button>
            )}
          </div>
        ))}
        <button type="button" onClick={addColor}>
          + Add color
        </button>
      </fieldset>

      <label>
        Formality
        <select value={value.formality} onChange={(e) => update("formality", e.target.value as Formality)} required>
          <option value="" disabled>
            Select formality
          </option>
          {FORMALITY_VALUES.map((f) => (
            <option key={f} value={f}>
              {f.replace("_", " ")}
            </option>
          ))}
        </select>
      </label>

      <label>
        Warmth (0 = airy, 5 = heaviest)
        <select
          value={value.warmth}
          onChange={(e) => update("warmth", e.target.value === "" ? "" : Number(e.target.value))}
          required
        >
          <option value="" disabled>
            Select warmth
          </option>
          {[0, 1, 2, 3, 4, 5].map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
      </label>

      <fieldset>
        <legend>Season (at least one)</legend>
        {SEASON_VALUES.map((s) => (
          <label key={s} className="checkbox-label">
            <input type="checkbox" checked={value.season.includes(s)} onChange={() => toggleSeason(s)} />
            {s}
          </label>
        ))}
      </fieldset>

      <label>
        Fabric
        <input type="text" value={value.fabric} onChange={(e) => update("fabric", e.target.value)} required />
      </label>

      <label>
        Pattern
        <input type="text" value={value.pattern} onChange={(e) => update("pattern", e.target.value)} required />
      </label>

      <label>
        Fit
        <input type="text" value={value.fit} onChange={(e) => update("fit", e.target.value)} required />
      </label>

      <button type="submit" disabled={!isComplete(value) || saving}>
        {saving ? "Saving…" : "Save to closet"}
      </button>
    </form>
  );
}

"use client";

import { useState } from "react";
import { CATEGORY_GROUPS, FORMALITY_VALUES, SEASON_VALUES, type Formality, type Season } from "@/lib/taxonomy";
import type { CreateWardrobeItemFromUploadRequest, ExtractedAttributes } from "@/lib/types";
import { useSignedPhotoUrl } from "@/lib/use-signed-photo-url";

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
  const photoUrl = useSignedPhotoUrl(photoPath);

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
      {photoUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={photoUrl} alt="The item you're adding" className="extracted-item-photo" />
      )}
      {!extractionOk && (
        <p className="extraction-warning">
          Couldn&apos;t confidently read this photo — fill in (or correct) the details below.
        </p>
      )}

      <div className="field">
        <label>Category</label>
        <div className="tag-toggle-group">
          {CATEGORY_GROUPS.map((c) => (
            <button
              key={c}
              type="button"
              className={value.category === c ? "chip chip-selected" : "chip"}
              aria-pressed={value.category === c}
              onClick={() => update("category", c)}
            >
              {c.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label>Colors</label>
        <div className="color-row">
          {value.colors.map((hex, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <input
                type="color"
                className="color-swatch-input selected"
                value={hex}
                onChange={(e) => updateColor(i, e.target.value)}
                aria-label={`Color ${i + 1}`}
              />
              {value.colors.length > 1 && (
                <button type="button" className="btn btn-ghost" style={{ fontSize: 11 }} onClick={() => removeColor(i)}>
                  Remove
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            className="color-swatch-input"
            style={{
              border: "1.5px dashed var(--color-divider)",
              background: "transparent",
              color: "var(--color-text)",
              fontSize: 18,
              lineHeight: "34px",
            }}
            onClick={addColor}
            aria-label="Add color"
          >
            +
          </button>
        </div>
      </div>

      <div className="field">
        <label>Formality</label>
        <div className="seg-track">
          {FORMALITY_VALUES.map((f) => (
            <button
              key={f}
              type="button"
              className={value.formality === f ? "seg-item seg-item-selected" : "seg-item"}
              aria-pressed={value.formality === f}
              onClick={() => update("formality", f)}
            >
              {f.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label>Warmth (0 = airy, 5 = heaviest)</label>
        <div className="tag-toggle-group">
          {[0, 1, 2, 3, 4, 5].map((w) => (
            <button
              key={w}
              type="button"
              className={value.warmth === w ? "chip chip-selected" : "chip"}
              aria-pressed={value.warmth === w}
              onClick={() => update("warmth", w)}
              style={{ minWidth: 36, justifyContent: "center", padding: "9px 0" }}
            >
              {w}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label>Season (at least one)</label>
        <div className="tag-toggle-group">
          {SEASON_VALUES.map((s) => (
            <button
              key={s}
              type="button"
              className={value.season.includes(s) ? "chip chip-selected" : "chip"}
              aria-pressed={value.season.includes(s)}
              onClick={() => toggleSeason(s)}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label htmlFor="fabric">Fabric</label>
        <input
          id="fabric"
          className="input"
          type="text"
          value={value.fabric}
          onChange={(e) => update("fabric", e.target.value)}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="pattern">Pattern</label>
        <input
          id="pattern"
          className="input"
          type="text"
          value={value.pattern}
          onChange={(e) => update("pattern", e.target.value)}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="fit">Fit</label>
        <input
          id="fit"
          className="input"
          type="text"
          value={value.fit}
          onChange={(e) => update("fit", e.target.value)}
          required
        />
      </div>

      <button type="submit" className="btn btn-primary btn-block" disabled={!isComplete(value) || saving}>
        {saving ? "Saving…" : "Save to closet"}
      </button>
    </form>
  );
}

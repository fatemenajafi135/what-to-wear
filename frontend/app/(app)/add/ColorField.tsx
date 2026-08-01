"use client";

import { Plus, X } from "lucide-react";
import styles from "./ColorField.module.css";

const HEX = /^#[0-9a-fA-F]{6}$/;

export function isHex(value: string): boolean {
  return HEX.test(value.trim());
}

export interface ColorFieldProps {
  values: string[];
  onChange: (values: string[]) => void;
  error?: string;
}

/**
 * Colour as **hex, shown as colour** — a swatch per entry beside its literal
 * `#rrggbb`, both editable, with add/remove. Mirrors the legacy app's own
 * control (`ExtractedItemForm`'s `<input type="color">` list) because that
 * was right: `colors.py` states hex is the source of truth and names are
 * derived, and `vision.py` returns hex.
 *
 * The version before this showed a name-only text field and sent the NAME
 * back, so the detected value went hex → nearest palette name → that name's
 * canonical hex — `#22345d` stored as navy's `#1b2a4a` — and a multi-colour
 * garment collapsed to a single entry. A name also can't be seen: "navy"
 * tells you nothing about which navy the scan actually read.
 *
 * The native `<input type="color">` is deliberate: it gives a real OS colour
 * picker on both mobile platforms for free, which no custom swatch grid
 * would match, and it cannot produce a non-hex value.
 */
export function ColorField({ values, onChange, error }: ColorFieldProps) {
  const update = (index: number, hex: string) => onChange(values.map((c, i) => (i === index ? hex : c)));
  const remove = (index: number) => onChange(values.filter((_, i) => i !== index));
  const add = () => onChange([...values, "#000000"]);

  return (
    <div className={styles.field}>
      <span className={`textLabel ${styles.label}`}>Color</span>

      {values.map((hex, i) => (
        <div key={i} className={styles.row}>
          <input
            type="color"
            // A malformed value would make the swatch fall back to black and
            // silently "correct" the text beside it, so only feed it valid hex.
            value={isHex(hex) ? hex : "#000000"}
            onChange={(e) => update(i, e.target.value)}
            className={styles.swatch}
            aria-label={`Color ${i + 1} swatch`}
          />
          <input
            type="text"
            value={hex}
            onChange={(e) => update(i, e.target.value)}
            className={`control ${styles.hex}`}
            aria-label={`Color ${i + 1} hex`}
            spellCheck={false}
            autoCapitalize="none"
          />
          <button
            type="button"
            className={`control ${styles.remove}`}
            onClick={() => remove(i)}
            aria-label={`Remove color ${i + 1}`}
          >
            <X size={16} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>
      ))}

      <button type="button" className={`control ${styles.add}`} onClick={add}>
        <Plus size={16} strokeWidth={2} aria-hidden="true" />
        Add color
      </button>

      {error && (
        <p className={`textBody ${styles.error}`} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

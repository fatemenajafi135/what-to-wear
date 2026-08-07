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
 * Colour as **swatches**. The value is hex throughout, but the hex is never
 * shown — a row of tappable colour wells, each with a remove control, plus
 * an add button. Mirrors the legacy app's own control (`ExtractedItemForm`'s
 * `<input type="color">` list).
 *
 * Two earlier versions were wrong in opposite directions. The first showed a
 * name-only text field and sent the NAME back, so the detected value went
 * hex → nearest palette name → that name's canonical hex (`#22345d` stored
 * as navy's `#1b2a4a`), and a multi-colour garment collapsed to one entry.
 * The second fixed the data but printed `#rrggbb` beside every swatch, which
 * puts a code where a colour belongs: the swatch already answers "which
 * colour" exactly and instantly, and the hex is machine detail nobody asked
 * to read.
 *
 * The native `<input type="color">` is deliberate — a real OS colour picker
 * on both mobile platforms for free, which no custom swatch grid would
 * match, and it cannot produce a non-hex value. With the text field gone, a
 * malformed colour is unreachable through the UI entirely; the validation
 * behind it stays as a guard on values arriving from the scan.
 */
export function ColorField({ values, onChange, error }: ColorFieldProps) {
  const update = (index: number, hex: string) => onChange(values.map((c, i) => (i === index ? hex : c)));
  const remove = (index: number) => onChange(values.filter((_, i) => i !== index));
  const add = () => onChange([...values, "#000000"]);

  return (
    <div className={styles.field}>
      <span className={`textLabel ${styles.label}`}>Color</span>

      <div className={styles.swatches}>
        {values.map((hex, i) => (
          <div key={i} className={styles.row}>
            <input
              type="color"
              // A malformed value would make the well fall back to black and
              // silently rewrite the stored value, so only feed it valid hex.
              value={isHex(hex) ? hex : "#000000"}
              onChange={(e) => update(i, e.target.value)}
              className={styles.swatch}
              aria-label={`Color ${i + 1}`}
            />
            <button
              type="button"
              className={styles.remove}
              onClick={() => remove(i)}
              aria-label={`Remove color ${i + 1}`}
            >
              <X size={12} strokeWidth={2.5} aria-hidden="true" />
            </button>
          </div>
        ))}

        <button type="button" className={styles.add} onClick={add} aria-label="Add color">
          <Plus size={18} strokeWidth={2} aria-hidden="true" />
        </button>
      </div>

      {error && (
        <p className={`textBody ${styles.error}`} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

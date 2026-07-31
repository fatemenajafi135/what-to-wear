import styles from "./BodyShapePicker.module.css";

export type BodyShape = "hourglass" | "pear" | "rectangle" | "apple" | "inverted_triangle";

export const BODY_SHAPE_OPTIONS: { value: BodyShape; label: string }[] = [
  { value: "hourglass", label: "Hourglass" },
  { value: "pear", label: "Pear" },
  { value: "rectangle", label: "Rectangle" },
  { value: "apple", label: "Apple" },
  { value: "inverted_triangle", label: "Inverted triangle" },
];

/**
 * Filled (not stroked) geometric silhouette — the stroke/size spec recorded
 * in docs/design-decisions.md resolving design-system.md's own "Open
 * questions" entry on this. viewBox 32x44; the read-only display renders it
 * at 26x36, the picker option box at 64x84 (sized by the parent via CSS).
 */
export function BodyShapeGlyph({ shape }: { shape: BodyShape }) {
  return (
    <svg viewBox="0 0 32 44" fill="currentColor" aria-hidden="true">
      <circle cx="16" cy="6" r="5" />
      {shape === "hourglass" && (
        <>
          <polygon points="6,13 26,13 21,25 11,25" />
          <polygon points="11,25 21,25 25,40 7,40" />
        </>
      )}
      {shape === "pear" && <polygon points="11,13 21,13 27,40 5,40" />}
      {shape === "rectangle" && <polygon points="8,13 24,13 24,40 8,40" />}
      {shape === "apple" && <polygon points="9,13 23,13 25,24 19,40 13,40 7,24" />}
      {shape === "inverted_triangle" && <polygon points="4,13 28,13 19,40 13,40" />}
    </svg>
  );
}

export interface BodyShapePickerProps {
  value: BodyShape | null;
  onChange: (value: BodyShape) => void;
  disabled?: boolean;
}

/**
 * FR-005: exactly one of five illustrated options, single-select. Follows
 * this codebase's `Chip` convention (independent `aria-pressed` buttons, not
 * a strict ARIA radiogroup) rather than inventing a second selection
 * pattern.
 */
export function BodyShapePicker({ value, onChange, disabled = false }: BodyShapePickerProps) {
  return (
    <div className={styles.row}>
      {BODY_SHAPE_OPTIONS.map((option) => {
        const active = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            aria-label={option.label}
            disabled={disabled}
            className={["control", styles.option, active ? styles.active : ""].join(" ")}
            onClick={() => onChange(option.value)}
          >
            <BodyShapeGlyph shape={option.value} />
            <span className="textLabel">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}

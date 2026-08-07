"use client";

import { useId } from "react";
import styles from "./DatePicker.module.css";

export interface DatePickerProps {
  label: string;
  value: string; // ISO date string, e.g. "1990-01-01"
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
}

function formatDisplay(isoValue: string): string | null {
  if (!isoValue) return null;
  const date = new Date(`${isoValue}T00:00:00`);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

/**
 * docs/design-decisions.md §1.5 DatePicker. Native <input type="date">,
 * styled as Input — kept native for correct mobile pickers/keyboard/AT
 * semantics. The design system's one existing date-formatting example
 * (toLocaleDateString long form) is shown as a readable preview alongside
 * the native control, which can't have its own picker UI restyled.
 */
export function DatePicker({ label, value, onChange, error, disabled = false }: DatePickerProps) {
  const id = useId();
  const messageId = `${id}-message`;
  const display = formatDisplay(value);

  return (
    <div className={styles.field}>
      <label htmlFor={id} className={`textLabel ${styles.label}`}>
        {label}
      </label>
      <input
        id={id}
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? messageId : undefined}
        className={["control", styles.input, error && styles.errorInput].filter(Boolean).join(" ")}
      />
      {display && <p className={`textCaption ${styles.display}`}>{display}</p>}
      {error && (
        <p id={messageId} className={`textCaption ${styles.errorText}`}>
          {error}
        </p>
      )}
    </div>
  );
}

"use client";

import { useId } from "react";
import { ChevronDown } from "lucide-react";
import styles from "./Select.module.css";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  error?: string;
  disabled?: boolean;
}

/**
 * docs/design-decisions.md §1.4 Select. Native <select> styled to match
 * Input, chevron-down drawn as a real element (not a background image, for
 * simplicity) with appearance:none on the control. Native select is kept
 * deliberately — no custom listbox — for correct mobile pickers, keyboard
 * behaviour and AT semantics.
 */
export function Select({ label, value, onChange, options, error, disabled = false }: SelectProps) {
  const id = useId();
  const messageId = `${id}-message`;

  return (
    <div className={styles.field}>
      <label htmlFor={id} className={`textLabel ${styles.label}`}>
        {label}
      </label>
      <div className={styles.selectWrap}>
        <select
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? messageId : undefined}
          className={["control", styles.select, error && styles.errorInput].filter(Boolean).join(" ")}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown size={16} className={styles.chevron} aria-hidden="true" />
      </div>
      {error && (
        <p id={messageId} className={`textCaption ${styles.errorText}`}>
          {error}
        </p>
      )}
    </div>
  );
}

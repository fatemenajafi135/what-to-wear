"use client";

import { useId } from "react";
import styles from "./Textarea.module.css";

export interface TextareaProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  helpText?: string;
  disabled?: boolean;
  placeholder?: string;
}

/**
 * docs/design-decisions.md §1.3 Textarea. Identical to Input except
 * min-height 94px (three rows), resize: vertical, line-height 1.5 — used
 * for Add-item Notes only.
 */
export function Textarea({ label, value, onChange, error, helpText, disabled = false, placeholder }: TextareaProps) {
  const id = useId();
  const messageId = `${id}-message`;

  return (
    <div className={styles.field}>
      <label htmlFor={id} className={`textLabel ${styles.label}`}>
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        aria-invalid={Boolean(error)}
        aria-describedby={error || helpText ? messageId : undefined}
        className={["control", styles.textarea, error && styles.errorInput].filter(Boolean).join(" ")}
      />
      {(error || helpText) && (
        <p id={messageId} className={`textCaption ${error ? styles.errorText : styles.helpText}`}>
          {error ?? helpText}
        </p>
      )}
    </div>
  );
}

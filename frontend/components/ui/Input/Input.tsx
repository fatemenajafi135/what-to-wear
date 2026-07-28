"use client";

import { useId, useState } from "react";
import { IconButton } from "@/components/ui/IconButton/IconButton";
import styles from "./Input.module.css";

export interface InputProps {
  type?: "text" | "email" | "password" | "number";
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  helpText?: string;
  disabled?: boolean;
  readOnly?: boolean;
  placeholder?: string;
}

/**
 * docs/design-decisions.md §1.2 Input. 44px height (11+22+11), 16px font at
 * every breakpoint (iOS zoom guard — not negotiable). Password fields carry
 * a show/hide toggle. Error replaces help text in the same slot rather than
 * stacking below it, so field height stays stable when validation fires.
 */
export function Input({
  type = "text",
  label,
  value,
  onChange,
  error,
  helpText,
  disabled = false,
  readOnly = false,
  placeholder,
}: InputProps) {
  const [showPassword, setShowPassword] = useState(false);
  const id = useId();
  const messageId = `${id}-message`;
  const isPassword = type === "password";
  const resolvedType = isPassword && showPassword ? "text" : type;

  return (
    <div className={styles.field}>
      <label htmlFor={id} className={`textLabel ${styles.label}`}>
        {label}
      </label>
      <div className={styles.inputWrap}>
        <input
          id={id}
          type={resolvedType}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          readOnly={readOnly}
          placeholder={placeholder}
          aria-invalid={Boolean(error)}
          aria-describedby={error || helpText ? messageId : undefined}
          className={["control", styles.input, isPassword && styles.withToggle, error && styles.errorInput]
            .filter(Boolean)
            .join(" ")}
        />
        {isPassword && (
          <span className={styles.toggle}>
            <IconButton
              icon={showPassword ? "eyeOff" : "eye"}
              size={28}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((v) => !v)}
            />
          </span>
        )}
      </div>
      {(error || helpText) && (
        <p id={messageId} className={`textCaption ${error ? styles.errorText : styles.helpText}`}>
          {error ?? helpText}
        </p>
      )}
    </div>
  );
}

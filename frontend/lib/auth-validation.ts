import { useState } from "react";

/**
 * docs/design-decisions.md §1.7 — field-level copy, verbatim. Form-level
 * errors (`auth.*.error.body`) are a separate mechanism (Banner), not this.
 */
export const authFieldMessages = {
  required: "This field is required.",
  emailInvalid: "Enter a valid email address.",
  passwordTooShort: "Use at least 8 characters.",
  passwordMismatch: "These passwords do not match.",
} as const;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 8;

export function validateEmail(value: string): string | undefined {
  if (!value) return authFieldMessages.required;
  if (!EMAIL_PATTERN.test(value)) return authFieldMessages.emailInvalid;
  return undefined;
}

export function validatePassword(value: string): string | undefined {
  if (!value) return authFieldMessages.required;
  if (value.length < MIN_PASSWORD_LENGTH) return authFieldMessages.passwordTooShort;
  return undefined;
}

export function validateConfirmPassword(password: string, confirmValue: string): string | undefined {
  if (!confirmValue) return authFieldMessages.required;
  if (confirmValue !== password) return authFieldMessages.passwordMismatch;
  return undefined;
}

type Validator = (value: string) => string | undefined;

/**
 * docs/design-decisions.md §1.7: "Validation fires on blur, never on
 * keystroke, and re-validates on every change once a field has already
 * errored." `onChange` therefore only recomputes the error while one is
 * already present; `onBlur` is the sole trigger for the first validation.
 */
export function useValidatedField(validate: Validator, initialValue = "") {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState<string | undefined>(undefined);

  function onChange(next: string) {
    setValue(next);
    setError((current) => (current ? validate(next) : current));
  }

  function onBlur() {
    setError(validate(value));
  }

  function reset(next = "") {
    setValue(next);
    setError(undefined);
  }

  return { value, error, onChange, onBlur, reset, setValue };
}

"use client";

import { useId, useState, type KeyboardEvent } from "react";
import { X } from "lucide-react";
import styles from "./TagInput.module.css";

export interface TagInputProps {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
}

/**
 * docs/design-decisions.md §1.6 TagInput. An Input-shaped container that
 * grows as chips wrap; each committed value is a Chip in its active state
 * with a trailing x remove button. Enter commits; Backspace on an empty
 * field removes the last chip. A visually-hidden live region announces
 * additions/removals for AT users.
 */
export function TagInput({ label, values, onChange, placeholder, disabled = false }: TagInputProps) {
  const [draft, setDraft] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const id = useId();

  const commitDraft = () => {
    const trimmed = draft.trim();
    if (!trimmed || values.includes(trimmed)) {
      setDraft("");
      return;
    }
    onChange([...values, trimmed]);
    setAnnouncement(`${trimmed} added`);
    setDraft("");
  };

  const removeValue = (value: string) => {
    onChange(values.filter((v) => v !== value));
    setAnnouncement(`${value} removed`);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commitDraft();
    } else if (event.key === "Backspace" && draft === "" && values.length > 0) {
      const last = values[values.length - 1];
      if (last !== undefined) removeValue(last);
    }
  };

  return (
    <div className={styles.field}>
      <label htmlFor={id} className={`textLabel ${styles.label}`}>
        {label}
      </label>
      <div className={styles.container} role="list">
        {values.map((value) => (
          <span key={value} role="listitem" className={styles.chip}>
            {value}
            <button
              type="button"
              className={styles.remove}
              aria-label={`Remove ${value}`}
              onClick={() => removeValue(value)}
              disabled={disabled}
            >
              <X size={12} strokeWidth={2.2} aria-hidden="true" />
            </button>
          </span>
        ))}
        <input
          id={id}
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={commitDraft}
          disabled={disabled}
          placeholder={values.length === 0 ? placeholder : undefined}
          className={styles.textInput}
        />
      </div>
      <p className="visuallyHidden" aria-live="polite">
        {announcement}
      </p>
    </div>
  );
}

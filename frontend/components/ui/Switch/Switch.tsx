"use client";

import type { KeyboardEvent } from "react";
import styles from "./Switch.module.css";

export interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  "aria-label"?: string;
}

/**
 * design/design-system.md §3 Switch. role="switch", aria-checked,
 * aria-disabled, keyboard-operable (Space/Enter), tabIndex 0 or -1 when
 * disabled. Hit area 44x44 despite the 42x24 visual track. Thumb-slide
 * transition is reduced-motion gated in Switch.module.css.
 */
export function Switch({ checked, onChange, disabled = false, ...rest }: SwitchProps) {
  const toggle = () => {
    if (!disabled) onChange(!checked);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      toggle();
    }
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-disabled={disabled || undefined}
      disabled={disabled}
      tabIndex={disabled ? -1 : 0}
      onClick={toggle}
      onKeyDown={handleKeyDown}
      className={styles.switch}
      {...rest}
    >
      <span className={styles.thumb} />
    </button>
  );
}

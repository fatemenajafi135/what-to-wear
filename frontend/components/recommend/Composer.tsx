"use client";

import { useState, type KeyboardEvent } from "react";
import { ArrowUp } from "lucide-react";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import styles from "./Composer.module.css";

export interface ComposerProps {
  onSend: (text: string) => void;
  /** Start-styling request in flight — disables the composer too (design-
   * system.md "Chat input behavior", intended not observed behavior). */
  inFlight: boolean;
}

/**
 * design/design-system.md § Screen anatomy → Recommend, item 6 + "Chat
 * input behavior": single-line `<input>` (never a growing textarea), pill
 * bar, 28px circular send button. Per docs/design-decisions.md §28, this
 * is local-only — it appends to the parent's transcript and never calls the
 * backend itself; "Start styling" is the one real network trigger.
 */
export function Composer({ onSend, inFlight }: ComposerProps) {
  const [value, setValue] = useState("");
  const isOnline = useOnlineStatus();
  const disabled = !isOnline || inFlight;

  function commit() {
    const text = value.trim();
    if (!text) return;
    onSend(text);
    setValue("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    }
  }

  return (
    <div className={styles.bar}>
      <input
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Style me…"
        disabled={disabled}
        className={styles.input}
        aria-label="Message"
      />
      <button
        type="button"
        onClick={commit}
        disabled={disabled || !value.trim()}
        className={["control", "hitArea", styles.send].join(" ")}
        aria-label="Send"
      >
        <ArrowUp size={16} strokeWidth={2.1} aria-hidden="true" />
      </button>
    </div>
  );
}

"use client";

import { useState, type KeyboardEvent } from "react";
import { ArrowUp, Loader2 } from "lucide-react";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import styles from "./Composer.module.css";

export interface ComposerProps {
  onSend: (text: string) => void;
  /** A conversational turn OR a Start-styling request is in flight —
   * disables the composer (design-system.md "Chat input behavior",
   * "Intended (production)": both `sending` and `styling` disable it). */
  inFlight: boolean;
}

/**
 * design/design-system.md § Screen anatomy → Recommend, item 6 + "Chat
 * input behavior". Single-line `<input>` (never a growing textarea), pill
 * bar, 28px circular send button. `onSend` is a synchronous report to the
 * parent (docs/design-decisions.md §37/§49) — `RecommendChat` is what
 * actually calls `POST /recommend/turns`, mirroring how it already owns
 * the one other real network trigger, "Start styling".
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
        aria-label={inFlight ? "Sending" : "Send"}
      >
        {inFlight ? (
          <Loader2 size={16} strokeWidth={2.1} aria-hidden="true" className={styles.spinner} />
        ) : (
          <ArrowUp size={16} strokeWidth={2.1} aria-hidden="true" />
        )}
      </button>
    </div>
  );
}

"use client";

import { useEffect, useState, type KeyboardEvent } from "react";
import { ArrowUp, Loader2 } from "lucide-react";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import styles from "./Composer.module.css";

export interface ComposerProps {
  onSend: (text: string) => void;
  /** A conversational turn OR a Start-styling request is in flight —
   * disables the composer (design-system.md "Chat input behavior",
   * "Intended (production)": both `sending` and `styling` disable it). */
  inFlight: boolean;
  /** specs/020-calendar-pick-to-recommend (design-decisions.md §61): a fresh conversation
   * with a picked event pre-fills this with editable, unsent text built from the event —
   * never asserted as fact, just an easy starting point. `pickedEventStore`'s hydration is
   * async, so this often arrives a render or two AFTER mount (found in manual verification,
   * T023: on a fresh page load the store hasn't hydrated yet when Composer first mounts, so
   * capturing it only as the `useState` initializer misses it entirely) — adopted whenever it
   * transitions to a real value WHILE the field is still untouched (`value === ""`), never
   * once the user has typed anything, so an edit in progress or a later change to which event
   * is picked can't clobber it. */
  initialValue?: string;
}

/**
 * design/design-system.md § Screen anatomy → Recommend, item 6 + "Chat
 * input behavior". Single-line `<input>` (never a growing textarea), pill
 * bar, 28px circular send button. `onSend` is a synchronous report to the
 * parent (docs/design-decisions.md §37/§49) — `RecommendChat` is what
 * actually calls `POST /recommend/turns`, mirroring how it already owns
 * the one other real network trigger, "Start styling".
 */
export function Composer({ onSend, inFlight, initialValue }: ComposerProps) {
  const [value, setValue] = useState(initialValue ?? "");
  const isOnline = useOnlineStatus();
  const disabled = !isOnline || inFlight;

  useEffect(() => {
    setValue((current) => (current === "" && initialValue ? initialValue : current));
  }, [initialValue]);

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

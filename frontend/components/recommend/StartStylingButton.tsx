"use client";

import { Button } from "@/components/ui/Button/Button";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import styles from "./StartStylingButton.module.css";

export interface StartStylingButtonProps {
  visible: boolean;
  /** True once ≥1 message has been composed since the last successful call. */
  hasPending: boolean;
  inFlight: boolean;
  onClick: () => void;
}

/**
 * design/design-system.md § Screen anatomy → Recommend, item 5. Per
 * docs/design-decisions.md §28, this — not the composer's own send — is the
 * one control that actually calls the backend. Disabled whenever there is
 * nothing new to send, a request is already in flight (no second concurrent
 * send, FR-012), or the client is offline (FR-013) — the composer's own
 * offline gate only covers local composing, not this network action.
 */
export function StartStylingButton({ visible, hasPending, inFlight, onClick }: StartStylingButtonProps) {
  const isOnline = useOnlineStatus();
  if (!visible) return null;

  return (
    <div className={styles.wrap}>
      <Button onClick={onClick} disabled={!hasPending || inFlight || !isOnline}>
        Start styling
      </Button>
      <p className={`textCaption ${styles.caption}`}>Uses everything you have told me so far</p>
    </div>
  );
}

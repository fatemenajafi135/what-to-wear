"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button/Button";
import { IconButton } from "@/components/ui/IconButton/IconButton";
import { useServiceWorkerUpdate } from "@/lib/pwa/useServiceWorkerUpdate";
import { updateToastCopy } from "@/lib/pwa/updateToastCopy";
import styles from "./UpdateToast.module.css";

/**
 * design/design-system.md §7 / "BottomSheet & toast motion" — position,
 * stacking and motion are fully specified (see UpdateToast.module.css);
 * copy is a flagged draft (lib/pwa/updateToastCopy.ts,
 * docs/design-decisions.md §53). `role="status" aria-live="polite"`, same
 * non-modal pattern as `Banner.tsx` — this never blocks interaction with
 * the rest of the page, so no focus trap.
 *
 * Mounted once in the root layout alongside `ServiceWorkerRegistration`.
 */
export function UpdateToast() {
  const { updateAvailable, accept, dismiss } = useServiceWorkerUpdate();
  // `mounted` controls DOM presence; `open` controls the enter/rest CSS
  // class; `dismissing` swaps in the faster exit transition timing for the
  // one moment it's needed. Three separate flags rather than overloading
  // `open` for "not yet shown" and "being dismissed" — those are different
  // states with different transition timings (base+decelerate to enter,
  // fast+accelerate to exit), not opposite ends of the same boolean.
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [dismissing, setDismissing] = useState(false);

  useEffect(() => {
    if (updateAvailable) {
      setMounted(true);
      setDismissing(false);
      // Next tick: mount at translateY(100%) first, then trigger the
      // transition to translateY(0) — a single-frame class flip wouldn't
      // transition at all.
      const id = requestAnimationFrame(() => setOpen(true));
      return () => cancelAnimationFrame(id);
    }
    setOpen(false);
  }, [updateAvailable]);

  function handleDismiss() {
    setOpen(false);
    setDismissing(true);
    dismiss();
    window.setTimeout(() => setMounted(false), 150);
  }

  if (!mounted) return null;

  return (
    <div
      className={[styles.toast, open && styles.open, dismissing && styles.closing].filter(Boolean).join(" ")}
      role="status"
      aria-live="polite"
    >
      <p className={`textBody ${styles.body}`}>{updateToastCopy.body}</p>
      <div className={styles.actions}>
        <Button variant="primary" width="intrinsic" onClick={accept}>
          {updateToastCopy.action}
        </Button>
        <IconButton icon="close" label={updateToastCopy.dismissLabel} onClick={handleDismiss} />
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";

interface ServiceWorkerUpdate {
  /** A new service worker is installed and waiting to activate. */
  updateAvailable: boolean;
  /** Tells the waiting worker to activate, then reloads once it takes control. */
  accept: () => void;
  /** Hides the toast for the rest of this page life (spec.md Clarifications). */
  dismiss: () => void;
}

/**
 * Reload-triggered detection only (spec.md Clarifications, 2026-08-05,
 * decided with the design owner): no `setInterval` + `registration.update()`
 * polling loop, no `visibilitychange` listener. Detection relies entirely on
 * the browser's own navigation-time service-worker update check — this hook
 * only notices the result of a check the browser already started on this
 * page's own load, via two independent signals:
 *
 * 1. `registration.waiting` already set on mount — the browser's check
 *    finished (on this or an earlier navigation) before this hook ran.
 * 2. `updatefound` → the new worker's `statechange` reaching `"installed"` —
 *    the browser's check, started by *this* navigation, finishes a moment
 *    after mount. Still one reload's worth of detection, not a new loop.
 *
 * `skipWaiting: false` in `app/sw.ts` (deliberately not overridden) is what
 * makes a newly-installed worker sit in `waiting` rather than taking over
 * unasked — this hook is what turns that `waiting` state into a user choice.
 */
export function useServiceWorkerUpdate(): ServiceWorkerUpdate {
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;

    let cancelled = false;

    navigator.serviceWorker.getRegistration().then((reg) => {
      if (cancelled || !reg) return;

      if (reg.waiting) {
        setRegistration(reg);
      }

      reg.addEventListener("updatefound", () => {
        const installing = reg.installing;
        if (!installing) return;
        installing.addEventListener("statechange", () => {
          // "installed" with an existing controller means a new version is
          // waiting, not the very first install of this page's own worker.
          if (installing.state === "installed" && navigator.serviceWorker.controller) {
            setRegistration(reg);
          }
        });
      });
    });

    return () => {
      cancelled = true;
    };
  }, []);

  function accept() {
    if (!registration?.waiting) return;
    navigator.serviceWorker.addEventListener(
      "controllerchange",
      () => {
        window.location.reload();
      },
      { once: true },
    );
    registration.waiting.postMessage({ type: "SKIP_WAITING" });
  }

  function dismiss() {
    setDismissed(true);
  }

  return {
    updateAvailable: registration?.waiting != null && !dismissed,
    accept,
    dismiss,
  };
}

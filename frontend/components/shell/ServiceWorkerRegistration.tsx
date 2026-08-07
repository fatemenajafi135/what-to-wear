"use client";

import { useEffect } from "react";

/**
 * Registers `public/sw.js` (built from `app/sw.ts` by `@serwist/next`) once,
 * on mount, in every display mode (browser tab and installed standalone —
 * registration is a page-level API with no display-mode branch,
 * Constitution IX / spec.md FR-013). No UI; mounted once in the root layout
 * so both the `(auth)` and `(app)` shells are covered.
 *
 * Serwist is disabled in development (`next.config.ts`), so `public/sw.js`
 * doesn't exist under `next dev` — registration is skipped there rather than
 * failing noisily.
 */
export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;

    navigator.serviceWorker.register("/sw.js").catch((error: unknown) => {
      console.error("Service worker registration failed", error);
    });
  }, []);

  return null;
}

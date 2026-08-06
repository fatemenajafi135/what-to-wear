/// <reference lib="webworker" />
// The rest of this app's tsconfig uses the "dom" lib (a service worker has no
// window); this directive pulls in "webworker" globals (ServiceWorkerGlobalScope,
// ExtendableEvent, caches) for this file only, without touching the project-wide
// tsconfig — the standard pattern for a Serwist/Workbox service worker in a
// Next.js app that otherwise targets the browser main thread everywhere else.

import { defaultCache } from "@serwist/next/worker";
import { CacheableResponsePlugin, CacheFirst, ExpirationPlugin, NetworkFirst, NetworkOnly, Serwist } from "serwist";
import type { PrecacheEntry, RuntimeCaching, SerwistGlobalConfig } from "serwist";
import { API_DATA_CACHE, PHOTOS_CACHE } from "@/lib/serviceWorker/cacheNames";

declare global {
  interface WorkerGlobalScope extends SerwistGlobalConfig {
    __SW_MANIFEST: (PrecacheEntry | string)[] | undefined;
  }
}

declare const self: ServiceWorkerGlobalScope;

/**
 * `contracts/route-caching.md` (specs/014-offline-and-updates) is the source
 * of truth for this table; `docs/design-decisions.md` §52 records why each
 * class is strategized the way it is. Computed at build time from the same
 * `NEXT_PUBLIC_*` env vars the rest of the app uses (`lib/api/client.ts`,
 * `lib/supabase/client.ts`) — Next's webpack build inlines these into the
 * service-worker bundle the same way it does for any other module.
 */
const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_URL!).origin;
const STORAGE_ORIGIN = new URL(process.env.NEXT_PUBLIC_SUPABASE_URL!).origin;

const isApiOrigin: RuntimeCaching["matcher"] = ({ url }) => url.origin === API_ORIGIN;

const isSignedPhotoUrl: RuntimeCaching["matcher"] = ({ url }) =>
  url.origin === STORAGE_ORIGIN && url.pathname.includes("/storage/v1/object/sign/");

// Class 3 — backend writes, explicitly NetworkOnly (research.md R4). Includes
// `POST /recommend/messages`, the billed/non-idempotent LLM call — never
// cached, never auto-retried. `RuntimeCaching.method` gates which requests a
// rule is even considered for, so one rule per non-GET method is needed
// (a single rule can't match "not GET").
const mutationRules: RuntimeCaching[] = (["POST", "PUT", "PATCH", "DELETE"] as const).map(
  (method) => ({
    method,
    matcher: isApiOrigin,
    handler: new NetworkOnly(),
  }),
);

const runtimeCaching: RuntimeCaching[] = [
  ...mutationRules,
  // Class 2 — backend reads.
  {
    method: "GET",
    matcher: isApiOrigin,
    handler: new NetworkFirst({
      cacheName: API_DATA_CACHE,
      networkTimeoutSeconds: 4,
      plugins: [new ExpirationPlugin({ maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 })],
    }),
  },
  // Class 4 — signed photo images. CacheFirst: a signed URL's bytes never
  // change for that exact URL (research.md R3 rejected alternative (c)), and
  // `maxAgeSeconds` matches the backend's own `wtw_photo_signed_url_ttl_seconds`.
  //
  // `statuses: [200]` only — NOT `[0, 200]`. `ItemPhoto`'s <img> now carries
  // `crossOrigin="anonymous"` (components/ui/ItemPhoto/ItemPhoto.tsx), so the
  // response this rule sees is a real, readable one, not opaque — this
  // plugin can finally tell a real photo from a failure apart. `[0, 200]` was
  // the original fix for "CacheFirst doesn't cache opaque responses by
  // default" (still true, see docs/design-decisions.md §52's first entry),
  // but it had its own defect: an opaque response's `status` is `0`
  // regardless of the real HTTP status, success or failure alike, so it
  // cached failures indistinguishably from photos — a photo that failed once
  // stayed broken from the cached failure for up to an hour, making zero
  // further network requests even once the same signed URL was healthy
  // again. Found in review, superseded here — see §52's amendment.
  {
    method: "GET",
    matcher: isSignedPhotoUrl,
    handler: new CacheFirst({
      cacheName: PHOTOS_CACHE,
      plugins: [
        new CacheableResponsePlugin({ statuses: [200] }),
        new ExpirationPlugin({ maxEntries: 300, maxAgeSeconds: 60 * 60 }),
      ],
    }),
  },
  // Class 1 — app shell (same-origin navigation, static assets, fonts). No
  // user data ever passes through this (research.md R1), so no purge concern.
  ...defaultCache,
];

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  // Deliberately not overridden to true: a newly-installed worker sits in
  // `waiting` rather than taking over unasked, which is what makes the
  // update prompt (lib/pwa/useServiceWorkerUpdate.ts) possible at all — the
  // single highest-risk item in this feature (handoff §6.1). It only
  // activates in response to the SKIP_WAITING message below, which only the
  // user's own "Update now" tap sends.
  skipWaiting: false,
  clientsClaim: true,
  navigationPreload: true,
  runtimeCaching,
});

serwist.addEventListeners();

// contracts/route-caching.md's update-prompt message contract.
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});

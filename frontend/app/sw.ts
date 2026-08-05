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
  // CacheableResponsePlugin({statuses: [0, 200]}) is not decoration: Supabase
  // Storage is a different origin, and `ItemPhoto`'s <img> has no
  // `crossorigin` attribute, so the browser requests it `no-cors` — the
  // response the service worker sees is opaque (`status === 0`). Serwist's
  // `NetworkFirst` auto-allows opaque responses in its own constructor;
  // `CacheFirst` does not, and silently declines to cache anything that
  // isn't exactly `status === 200` without this plugin (confirmed empirically
  // while writing e2e-pwa/service-worker-smoke.spec.ts — every photo request
  // succeeded but `wtw-photos` stayed empty until this was added).
  {
    method: "GET",
    matcher: isSignedPhotoUrl,
    handler: new CacheFirst({
      cacheName: PHOTOS_CACHE,
      plugins: [
        new CacheableResponsePlugin({ statuses: [0, 200] }),
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
  skipWaiting: false,
  clientsClaim: true,
  navigationPreload: true,
  runtimeCaching,
});

serwist.addEventListeners();

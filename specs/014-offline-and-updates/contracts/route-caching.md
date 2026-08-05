# Contract: service worker route-caching table

This is the "interface" this feature exposes internally — the contract between application code
and `app/sw.ts` that a reviewer (or a unit test) can check without reading the whole service
worker. Restates `research.md` R3 in matcher form; `research.md` holds the reasoning, this is the
literal shape `runtimeCaching` must have.

```ts
// app/sw.ts — runtimeCaching array, evaluated in order, first match wins.
// Prepended before @serwist/next/worker's `defaultCache` (which owns class 1).

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_URL!).origin;
const STORAGE_ORIGIN = new URL(process.env.NEXT_PUBLIC_SUPABASE_URL!).origin;

runtimeCaching: [
  // Class 3 — backend writes, explicitly NetworkOnly (research.md R4).
  // Includes POST /recommend/messages; must never be reordered below class 2.
  {
    matcher: ({ url, request }) =>
      url.origin === API_ORIGIN && request.method !== "GET",
    handler: "NetworkOnly",
  },

  // Class 2 — backend reads.
  {
    matcher: ({ url, request }) =>
      url.origin === API_ORIGIN && request.method === "GET",
    handler: "NetworkFirst",
    options: {
      cacheName: API_DATA_CACHE, // "wtw-api-data"
      networkTimeoutSeconds: 4,
      expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 },
    },
  },

  // Class 4 — signed photo images.
  {
    matcher: ({ url }) =>
      url.origin === STORAGE_ORIGIN && url.pathname.includes("/storage/v1/object/sign/"),
    handler: "CacheFirst",
    options: {
      cacheName: PHOTOS_CACHE, // "wtw-photos"
      expiration: { maxEntries: 300, maxAgeSeconds: 3600 },
    },
  },

  // Class 1 (app shell) comes from @serwist/next/worker's defaultCache, appended after this array.
],
```

## Invariants a test can assert directly

1. `POST /recommend/messages` never matches anything but the class-3 `NetworkOnly` rule (route
   order test — construct the matcher list, assert the mutation matcher wins for that exact
   request shape before the GET-scoped rule is even reachable).
2. `API_DATA_CACHE` and `PHOTOS_CACHE` are exactly `USER_SCOPED_CACHE_NAMES`
   (`lib/serviceWorker/cacheNames.ts`) — the purge list and the route table can't drift apart
   because both import the same constants.
3. No `runtimeCaching` entry anywhere in `sw.ts` has `handler` other than `"NetworkOnly"` for a
   non-`GET` method against `API_ORIGIN`.

## Sign-out purge contract

```ts
// lib/auth/signOut.ts
export async function signOutAndClearCache(supabase: SupabaseClient): Promise<void> {
  await supabase.auth.signOut();
  if (typeof caches !== "undefined") {
    await Promise.all(USER_SCOPED_CACHE_NAMES.map((name) => caches.delete(name)));
  }
}
```

Both existing sign-out call sites (`app/(app)/profile/page.tsx`, `components/auth/
ResetPasswordForm.tsx`) call this instead of `supabase.auth.signOut()` directly.

## Update-prompt message contract

```ts
// Client → waiting worker
registration.waiting?.postMessage({ type: "SKIP_WAITING" });

// sw.ts
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});

// Client, one-time listener registered before postMessage above
navigator.serviceWorker.addEventListener("controllerchange", () => location.reload(), { once: true });
```

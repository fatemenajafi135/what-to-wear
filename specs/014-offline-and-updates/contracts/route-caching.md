# Contract: service worker route-caching table

This is the "interface" this feature exposes internally — the contract between application code
and `app/sw.ts` that a reviewer (or a unit test) can check without reading the whole service
worker. Restates `research.md` R3 in matcher form; `research.md` holds the reasoning, this is the
literal shape `runtimeCaching` must have.

Serwist's `RuntimeCaching.handler` is a `Strategy` **instance**, not a string enum name (this
contract originally drafted it as a string during planning — corrected once implementation showed
the real `serwist` package API). `method` is its own field, not folded into the matcher — a single
entry can't match "not GET", so class 3 is one entry per mutating method.

```ts
// app/sw.ts — runtimeCaching array, evaluated in order, first match wins.
// Prepended before @serwist/next/worker's `defaultCache` (which owns class 1).

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_URL!).origin;
const STORAGE_ORIGIN = new URL(process.env.NEXT_PUBLIC_SUPABASE_URL!).origin;
const isApiOrigin: RuntimeCaching["matcher"] = ({ url }) => url.origin === API_ORIGIN;
const isSignedPhotoUrl: RuntimeCaching["matcher"] = ({ url }) =>
  url.origin === STORAGE_ORIGIN && url.pathname.includes("/storage/v1/object/sign/");

runtimeCaching: [
  // Class 3 — backend writes, explicitly NetworkOnly (research.md R4).
  // Includes POST /recommend/messages; must never be reordered below class 2.
  // One entry per method — RuntimeCaching.method gates the request before
  // the matcher runs, so a single entry cannot express "any non-GET".
  ...(["POST", "PUT", "PATCH", "DELETE"] as const).map((method) => ({
    method,
    matcher: isApiOrigin,
    handler: new NetworkOnly(),
  })),

  // Class 2 — backend reads.
  {
    method: "GET",
    matcher: isApiOrigin,
    handler: new NetworkFirst({
      cacheName: API_DATA_CACHE, // "wtw-api-data"
      networkTimeoutSeconds: 4,
      plugins: [new ExpirationPlugin({ maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 })],
    }),
  },

  // Class 4 — signed photo images. CacheableResponsePlugin is required, not
  // optional decoration: ItemPhoto's <img> has no `crossorigin` attribute,
  // so a cross-origin photo request is `no-cors` and the response the SW
  // sees is opaque (status 0). CacheFirst — unlike NetworkFirst, which
  // auto-allows this in its own constructor — only caches exact status 200
  // by default, so without this plugin every photo request "succeeds" (200
  // on the wire) while wtw-photos silently stays empty (research.md R3,
  // found by asserting real caches.keys() contents, not by trusting config).
  {
    method: "GET",
    matcher: isSignedPhotoUrl,
    handler: new CacheFirst({
      cacheName: PHOTOS_CACHE, // "wtw-photos"
      plugins: [
        new CacheableResponsePlugin({ statuses: [0, 200] }),
        new ExpirationPlugin({ maxEntries: 300, maxAgeSeconds: 3600 }),
      ],
    }),
  },

  // Class 1 (app shell) comes from @serwist/next/worker's defaultCache, appended after this array.
  ...defaultCache,
],
```

## Invariants a test can assert directly

1. `POST /recommend/messages` never matches anything but a class-3 `NetworkOnly` entry (route
   order test — construct the matcher list, assert the mutation matcher wins for that exact
   request shape before the GET-scoped rule is even reachable).
2. `API_DATA_CACHE` and `PHOTOS_CACHE` are exactly `USER_SCOPED_CACHE_NAMES`
   (`lib/serviceWorker/cacheNames.ts`) — the purge list and the route table can't drift apart
   because both import the same constants.
3. No `runtimeCaching` entry anywhere in `sw.ts` uses anything but `NetworkOnly` for a non-`GET`
   method against `API_ORIGIN`.
4. Class 4's plugin list includes a `CacheableResponsePlugin` (or equivalent `cacheWillUpdate`
   hook) that accepts `status 0` — its absence is silent (no error, no log a test would catch
   without inspecting actual `Cache` contents), so this is worth asserting explicitly rather than
   trusting the plugin array's presence alone.

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

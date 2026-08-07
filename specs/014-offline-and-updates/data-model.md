# Data model: Offline, caching and the update prompt

No database schema changes (no migration expected, per the handoff header — confirmed: this
feature touches no `infra/supabase/migrations/`, no backend model). The only "data" this feature
introduces lives in the browser's own Cache Storage and a small amount of in-memory client state.

## Cache Storage namespaces

| Cache name | Owner (route class, `research.md` R3) | Entry shape | Lifetime | Purged at sign-out |
|---|---|---|---|---|
| Serwist/Workbox precache (auto-named) | Class 1 — app shell | Next.js build output: JS/CSS chunks, RSC payloads referenced by the precache manifest | Until the next SW version's `activate` step prunes stale entries | No |
| `wtw-api-data` | Class 2 — backend API GET reads | `Request` (full URL incl. query) → `Response` (JSON body) | `maxAgeSeconds: 86400`, `maxEntries: 200` (`ExpirationPlugin`) | **Yes** |
| `wtw-photos` | Class 4 — signed photo images | `Request` (signed URL incl. token) → `Response` (image bytes) | `maxAgeSeconds: 3600` (matches `wtw_photo_signed_url_ttl_seconds`), `maxEntries: 300` | **Yes** |

Class 3 (backend API writes, including `POST /recommend/messages`) stores nothing — `NetworkOnly`
by design (`research.md` R3/R4).

## Client-side runtime state (not persisted)

| State | Where it lives | Shape | Notes |
|---|---|---|---|
| Waiting service worker registration | `useServiceWorkerUpdate()` hook, component state | `ServiceWorkerRegistration \| null` | Set once per page load when a waiting worker is found (`research.md` R7); never written to `localStorage`/`sessionStorage`. |
| Update-toast dismissed flag | Same hook, component state | `boolean` | Resets naturally on the next real page load — no persistence needed given reload-triggered-only detection (`spec.md` Clarifications). |
| Broken-photo fallback flag | `ItemPhoto`, component state | `boolean` (`hasError`) | Set by the `<img>` element's `onError`; renders `NoPhoto` once true (`research.md` R6). Scoped to that one mounted instance, not global. |

## Cache-name constants (single source, referenced by both the SW and the client)

```
frontend/lib/serviceWorker/cacheNames.ts
  export const API_DATA_CACHE = "wtw-api-data";
  export const PHOTOS_CACHE = "wtw-photos";
  export const USER_SCOPED_CACHE_NAMES = [API_DATA_CACHE, PHOTOS_CACHE] as const;
```

`app/sw.ts` imports these two names when constructing its `runtimeCaching` rules;
`lib/auth/signOut.ts` imports `USER_SCOPED_CACHE_NAMES` for the purge. One definition, two
consumers — prevents the purge list and the cache-name list from drifting apart.

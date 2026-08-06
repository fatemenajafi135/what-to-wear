/**
 * Single source for the two Cache Storage names that can hold
 * authenticated, user-scoped data (backend API reads, signed photo
 * images — docs/design-decisions.md §52). `app/sw.ts` and
 * `lib/auth/signOut.ts` both import this file so the sign-out purge list
 * can never drift from the route table that populates these caches.
 *
 * Deliberately excludes the Serwist/Workbox precache (the app shell):
 * that cache holds no user data (every authenticated screen fetches its
 * data client-side against a separate API origin — research.md R1) and
 * must survive sign-out so the next offline cold start still has
 * something to render.
 */
export const API_DATA_CACHE = "wtw-api-data";
export const PHOTOS_CACHE = "wtw-photos";

export const USER_SCOPED_CACHE_NAMES = [API_DATA_CACHE, PHOTOS_CACHE] as const;

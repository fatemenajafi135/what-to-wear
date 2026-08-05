import type { createClient } from "@/lib/supabase/client";
import { USER_SCOPED_CACHE_NAMES } from "@/lib/serviceWorker/cacheNames";

/**
 * Wraps `supabase.auth.signOut()` with the sign-out cache purge
 * (docs/design-decisions.md §52): deletes the two Cache Storage entries
 * that can hold authenticated data, by name, from the page — `caches` is
 * available on `window`, no need to message the service worker. Named
 * caches only, never `caches.keys()` + delete-everything: that would also
 * wipe the app-shell precache, which holds no user data (research.md R1)
 * and would otherwise leave the next offline cold start on this device
 * with nothing to render until a new service-worker cycle repopulates it.
 *
 * Both existing sign-out call sites (`app/(app)/profile/page.tsx`,
 * `components/auth/ResetPasswordForm.tsx`) call this instead of
 * `supabase.auth.signOut()` directly, so the purge can't be added to one
 * and forgotten on the other.
 */
export async function signOutAndClearCache(supabase: ReturnType<typeof createClient>): Promise<void> {
  await supabase.auth.signOut();
  if (typeof caches !== "undefined") {
    await Promise.all(USER_SCOPED_CACHE_NAMES.map((name) => caches.delete(name)));
  }
}

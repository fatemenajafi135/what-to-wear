const PRIMED_KEY = "wtw_camera_primed";

/**
 * Gates the camera permission primer so it appears once, not on every
 * upload attempt (known-gaps.md §-2, spec.md FR-009). Mirrors
 * lib/calendar/primed.ts exactly. `localStorage` is unavailable during
 * SSR — both functions are safe to call from a Server Component (a false
 * negative there just means a client-side check runs again on hydration,
 * never a crash).
 */
export function isCameraPrimed(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(PRIMED_KEY) === "true";
}

export function setCameraPrimed(): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PRIMED_KEY, "true");
}

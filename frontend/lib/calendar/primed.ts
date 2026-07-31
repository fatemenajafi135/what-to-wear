const PRIMED_KEY = "wtw_calendar_primed";

/**
 * Gates the calendar permission primer so it appears once, not on every
 * connect attempt (known-gaps.md §-2, spec.md FR-002). `localStorage` is
 * unavailable during SSR — both functions are safe to call from a Server
 * Component (a false negative there just means a client-side check runs
 * again on hydration, never a crash).
 */
export function isCalendarPrimed(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(PRIMED_KEY) === "true";
}

export function setCalendarPrimed(): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PRIMED_KEY, "true");
}

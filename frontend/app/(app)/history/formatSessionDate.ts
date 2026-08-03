/**
 * design-system.md §6/§ Date & time formats: a session row's date label —
 * shared by the Chat history list and Session detail's own subtitle so the
 * two surfaces always agree (docs/design-decisions.md's convention: the
 * detail subtitle "should just reuse that same string unmodified, not
 * reformat it"). Same "Today" / short-month-day shape `OutfitsGrid.tsx`'s
 * `formatOutfitDate` already uses for the identical prototype convention
 * ("Today", "Jul 20").
 */
export function formatSessionDate(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) return "Today";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

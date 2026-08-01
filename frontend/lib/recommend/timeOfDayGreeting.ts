/**
 * design/design-system.md §9: "Good morning" (00:00–11:59), "Good afternoon"
 * (12:00–17:59), "Good evening" (18:00–23:59), device local time. The
 * prototype hardcoded "Good afternoon" always — known-gaps.md §0.7.
 */
export function greetingFor(hour: number): "Good morning" | "Good afternoon" | "Good evening" {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

/**
 * docs/design-decisions.md §29: no display-name field exists anywhere in
 * the app (Settings only has email) — the greeting's "{name}" is derived
 * from the email local-part, title-cased on common separators.
 */
export function nameFromEmail(email: string | null | undefined): string {
  if (!email) return "there";
  const localPart = email.split("@")[0] ?? "";
  if (!localPart) return "there";
  const words = localPart.split(/[._\-+]+/).filter(Boolean);
  if (words.length === 0) return "there";
  return words.map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
}

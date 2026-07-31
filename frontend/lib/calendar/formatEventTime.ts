/**
 * Computes the "{relative day}, {h:mm AM/PM}" label design-system.md's
 * "Date & time formats" specifies for Calendar event rows — from the
 * event's real timestamp, never a hardcoded string (spec.md FR-006).
 *
 * Relative-day rule: Today / Tomorrow / a weekday name for the next ~6 days
 * (days 2-6 out) / a short date beyond that. Time is locale-aware
 * (`toLocaleTimeString`), matching the one other real date-formatting
 * example already in this codebase (Settings' birth date, per
 * design-system's own note).
 */

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export function formatEventTime(startIso: string, now: Date = new Date()): string {
  const start = new Date(startIso);
  const dayDiff = Math.round((startOfDay(start).getTime() - startOfDay(now).getTime()) / 86_400_000);

  let relativeDay: string;
  if (dayDiff === 0) {
    relativeDay = "Today";
  } else if (dayDiff === 1) {
    relativeDay = "Tomorrow";
  } else if (dayDiff >= 2 && dayDiff <= 6) {
    relativeDay = start.toLocaleDateString(undefined, { weekday: "long" });
  } else {
    relativeDay = start.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  const time = start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${relativeDay}, ${time}`;
}

import { describe, expect, it } from "vitest";
import { formatEventTime } from "./formatEventTime";

// Fixed "now": Wednesday 2026-08-05, 12:00 local.
const NOW = new Date(2026, 7, 5, 12, 0, 0);

describe("formatEventTime", () => {
  it("labels an event later today as Today", () => {
    const label = formatEventTime(new Date(2026, 7, 5, 19, 30).toISOString(), NOW);
    expect(label).toMatch(/^Today, /);
  });

  it("labels an event tomorrow as Tomorrow", () => {
    const label = formatEventTime(new Date(2026, 7, 6, 9, 0).toISOString(), NOW);
    expect(label).toMatch(/^Tomorrow, /);
  });

  it("labels an event 3 days out with its weekday name", () => {
    // NOW is Wednesday; +3 days is Saturday.
    const label = formatEventTime(new Date(2026, 7, 8, 10, 0).toISOString(), NOW);
    expect(label).toMatch(/^Saturday, /);
  });

  it("labels an event 6 days out with its weekday name", () => {
    const label = formatEventTime(new Date(2026, 7, 11, 10, 0).toISOString(), NOW);
    expect(label).toMatch(/^Tuesday, /);
  });

  it("labels an event 7+ days out with a short date, not a weekday", () => {
    const label = formatEventTime(new Date(2026, 7, 12, 10, 0).toISOString(), NOW);
    expect(label.startsWith("Today")).toBe(false);
    expect(label.startsWith("Tomorrow")).toBe(false);
    expect(label).toMatch(/^Aug 12, /);
  });

  it("includes a locale-aware time, not a 24-hour bare string", () => {
    const label = formatEventTime(new Date(2026, 7, 5, 19, 30).toISOString(), NOW);
    expect(label).toMatch(/\d{1,2}:\d{2}\s?[AP]M$/i);
  });

  it("never hardcodes the string 'Today, 7:30 PM' regardless of input", () => {
    const label = formatEventTime(new Date(2026, 7, 20, 8, 15).toISOString(), NOW);
    expect(label).not.toBe("Today, 7:30 PM");
  });
});

import { describe, expect, it } from "vitest";
import { greetingFor, nameFromEmail } from "./timeOfDayGreeting";

describe("greetingFor", () => {
  it.each([
    [0, "Good morning"],
    [11, "Good morning"],
    [12, "Good afternoon"],
    [17, "Good afternoon"],
    [18, "Good evening"],
    [23, "Good evening"],
  ])("hour %i -> %s", (hour, expected) => {
    expect(greetingFor(hour)).toBe(expected);
  });
});

describe("nameFromEmail", () => {
  it("title-cases a dotted local part", () => {
    expect(nameFromEmail("jane.doe@example.com")).toBe("Jane Doe");
  });

  it("capitalizes a single-word local part", () => {
    expect(nameFromEmail("maya@example.com")).toBe("Maya");
  });

  it("handles underscore and hyphen separators", () => {
    expect(nameFromEmail("jane_doe-smith@example.com")).toBe("Jane Doe Smith");
  });

  it("falls back to 'there' for a missing email", () => {
    expect(nameFromEmail(null)).toBe("there");
    expect(nameFromEmail(undefined)).toBe("there");
    expect(nameFromEmail("")).toBe("there");
  });
});

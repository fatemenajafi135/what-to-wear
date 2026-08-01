import { describe, expect, it } from "vitest";
import { isRecognizedColorName } from "./validateColorName";

describe("isRecognizedColorName", () => {
  it("accepts an exact palette name", () => {
    expect(isRecognizedColorName("navy")).toBe(true);
  });

  it("accepts case-insensitive and trimmed variants", () => {
    expect(isRecognizedColorName("  Navy  ")).toBe(true);
    expect(isRecognizedColorName("NAVY")).toBe(true);
  });

  it("accepts a hex value", () => {
    expect(isRecognizedColorName("#1b2a4a")).toBe(true);
    expect(isRecognizedColorName("1b2a4a")).toBe(true);
  });

  it("rejects an unrecognized name", () => {
    expect(isRecognizedColorName("mauve")).toBe(false);
  });

  it("rejects an empty string", () => {
    expect(isRecognizedColorName("")).toBe(false);
  });
});

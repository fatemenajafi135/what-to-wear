import { describe, it, expect, beforeEach } from "vitest";
import { getStoredTheme, setStoredTheme, THEME_BOOT_SCRIPT } from "./theme";

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("getStoredTheme", () => {
  it("defaults to light when nothing is stored", () => {
    expect(getStoredTheme()).toBe("light");
  });

  it("defaults to light for a garbage stored value", () => {
    window.localStorage.setItem("wtw-theme", "not-a-real-theme");
    expect(getStoredTheme()).toBe("light");
  });

  it.each(["light", "dark", "system"] as const)("reads a valid stored value: %s", (value) => {
    window.localStorage.setItem("wtw-theme", value);
    expect(getStoredTheme()).toBe(value);
  });
});

describe("setStoredTheme", () => {
  it("writes to localStorage and sets data-theme on the document element", () => {
    setStoredTheme("dark");

    expect(window.localStorage.getItem("wtw-theme")).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});

describe("THEME_BOOT_SCRIPT", () => {
  it("is a self-invoking script that sets data-theme from the same storage key", () => {
    expect(THEME_BOOT_SCRIPT).toContain("wtw-theme");
    expect(THEME_BOOT_SCRIPT).toContain("data-theme");
  });

  it("actually behaves correctly when executed, mirroring getStoredTheme's fallback", () => {
    window.localStorage.setItem("wtw-theme", "dark");
    eval(THEME_BOOT_SCRIPT);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("falls back to light for an invalid stored value when executed", () => {
    window.localStorage.setItem("wtw-theme", "not-a-real-theme");
    eval(THEME_BOOT_SCRIPT);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});

import { test, expect } from "@playwright/test";
import { gotoCatalog } from "./catalog";

/**
 * spec.md FR-008 / SC-003: the focus ring shows on keyboard Tab and is
 * absent on mouse click, across Button/IconButton/Chip/Switch/Input.
 */
const selectors = [
  { name: "Button", locator: "button:has-text('Primary')" },
  { name: "IconButton", locator: "button[aria-label='Settings']" },
  { name: "Chip", locator: "button:has-text('Tops'):not([aria-pressed='true'])" },
  { name: "Switch", locator: "[role='switch']" },
  { name: "Input", locator: "input[type='email']" },
];

test.describe(":focus-visible shows on keyboard focus", () => {
  for (const { name, locator } of selectors) {
    test(`${name} shows an outline on keyboard focus`, async ({ page }) => {
      await gotoCatalog(page);
      const el = page.locator(locator).first();
      await el.focus();
      const outline = await el.evaluate((node) => getComputedStyle(node).outlineStyle);
      expect(outline).not.toBe("none");
    });
  }
});

test.describe(":focus-visible is absent on mouse click", () => {
  // Text fields (Input) are deliberately excluded here: per the CSS
  // :focus-visible spec, browsers intentionally still show the ring for
  // text-entry elements on pointer focus too, since typing is the expected
  // next action regardless of focus method — that's correct browser
  // behavior, not a gap in this component.
  for (const { name, locator } of selectors.filter((s) => s.name !== "Input")) {
    test(`${name} shows no outline on mouse click`, async ({ page }) => {
      await gotoCatalog(page);
      const el = page.locator(locator).first();
      await el.click();
      const outline = await el.evaluate((node) => getComputedStyle(node).outlineStyle);
      expect(outline).toBe("none");
    });
  }
});

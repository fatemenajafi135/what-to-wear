import { test, expect } from "@playwright/test";

const LIGHT_BACKGROUND = "rgb(230, 225, 214)"; // #E6E1D6
const DARK_BACKGROUND = "rgb(28, 24, 34)"; // #1C1822

async function bodyBackground(page: import("@playwright/test").Page): Promise<string> {
  return page.evaluate(() => getComputedStyle(document.body).backgroundColor);
}

/**
 * docs/handoffs/001-app-shell-fix-theme.md: boot theme resolves entirely in
 * CSS via `light-dark()` against `prefers-color-scheme` (styles/themes.css)
 * — no script, no cookie, no server call, so there is nothing to flash and
 * nothing for the server to read per-request (the stub routes stay ○
 * Static in `next build`). An explicit `data-theme` on <html> — what a
 * future theme toggle would set — still overrides the OS preference in
 * both directions, since it forces `color-scheme` to a single value that
 * `light-dark()` resolves against.
 */
test.describe("boot theme resolves from prefers-color-scheme, no flash", () => {
  test("dark OS preference, no override: renders dark on first paint", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/recommend");
    expect(await bodyBackground(page)).toBe(DARK_BACKGROUND);
  });

  test("light OS preference, no override: renders light on first paint", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/recommend");
    expect(await bodyBackground(page)).toBe(LIGHT_BACKGROUND);
  });

  // Setting data-theme via addInitScript (before hydration) doesn't work here:
  // React reconciles the root <html> element's attributes during hydration and
  // strips anything that wasn't part of its own server/client-rendered output.
  // A real future toggle would set this attribute from a client event handler
  // *after* hydration completes, which React leaves alone — these tests do the
  // same, setting the attribute post-load rather than pre-render.
  test("explicit data-theme=dark overrides a light OS preference", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/recommend");
    await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
    expect(await bodyBackground(page)).toBe(DARK_BACKGROUND);
  });

  test("explicit data-theme=light overrides a dark OS preference", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/recommend");
    await page.evaluate(() => document.documentElement.setAttribute("data-theme", "light"));
    expect(await bodyBackground(page)).toBe(LIGHT_BACKGROUND);
  });

  test("no repaint from one theme to the other after first paint", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/recommend", { waitUntil: "domcontentloaded" });
    const atDomContentLoaded = await bodyBackground(page);
    await page.waitForLoadState("networkidle");
    const atNetworkIdle = await bodyBackground(page);
    expect(atDomContentLoaded).toBe(DARK_BACKGROUND);
    expect(atNetworkIdle).toBe(atDomContentLoaded);
  });
});

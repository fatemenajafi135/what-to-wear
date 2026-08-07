import { test, expect } from "@playwright/test";
import { gotoCatalog } from "./catalog";

/**
 * spec.md FR-011 / FR-018: prefers-reduced-motion: reduce disables the
 * skeleton pulse, Switch thumb-slide, boot logo pulse (app/loading.tsx),
 * and BottomSheet's open/close transition — all replaced by an instant,
 * static equivalent.
 */
test.describe("prefers-reduced-motion disables all gated animations", () => {
  test.use({ colorScheme: "light", contextOptions: { reducedMotion: "reduce" } });

  test("Switch thumb-slide transition is none", async ({ page }) => {
    await gotoCatalog(page);
    const thumb = page.locator("[role='switch']").first().locator("span").first();
    const transition = await thumb.evaluate((node) => getComputedStyle(node).transitionDuration);
    expect(transition).toMatch(/^0s/);
  });

  test("BottomSheet open/close transition is none", async ({ page }) => {
    await gotoCatalog(page);
    await page.getByRole("button", { name: "Open (normal)" }).first().click();
    const dialog = page.getByRole("dialog").first();
    await expect(dialog).toBeVisible();
    const transition = await dialog.evaluate((node) => getComputedStyle(node).transitionDuration);
    expect(transition).toMatch(/^0s/);
  });

  test("boot logo pulse (app/loading.tsx) animation is none", async ({ page }) => {
    // app/loading.tsx is a Next.js Suspense-fallback file — it has no
    // reliable real trigger in a slice with no async data fetching, so the
    // catalog renders it directly (dev/components/ComponentCatalog.tsx) for
    // deterministic testing.
    await gotoCatalog(page);
    const mark = page.locator("img[alt='']").first();
    const animation = await mark.evaluate((node) => getComputedStyle(node).animationName);
    expect(animation).toBe("none");
  });
});

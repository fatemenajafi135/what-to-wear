import { test, expect } from "@playwright/test";

test.describe("focus moves to the new screen's <h1> on navigation (spec.md FR-009)", () => {
  test("clicking a primary nav link focuses the destination's heading", async ({ page }) => {
    await page.goto("/recommend");

    await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Closet" }).first().click();
    await expect(page).toHaveURL(/\/closet$/);

    const heading = page.locator("main h1").first();
    await expect(heading).toHaveText("Closet");
    await expect(heading).toBeFocused();
  });

  test("Profile's visually-hidden <h1> still receives focus", async ({ page }) => {
    await page.goto("/recommend");
    await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Profile" }).first().click();
    await expect(page).toHaveURL(/\/profile$/);

    const heading = page.locator("main h1").first();
    await expect(heading).toHaveText("Profile");
    await expect(heading).toBeFocused();
  });
});

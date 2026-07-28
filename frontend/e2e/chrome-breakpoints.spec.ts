import { test, expect } from "@playwright/test";

const DESTINATIONS = ["Recommend", "Closet", "Outfits", "Profile"];

test.describe("responsive chrome @ four reference widths (spec.md FR-001, SC-001)", () => {
  test("all four destinations are reachable, with only the chrome changing", async ({
    page,
  }, testInfo) => {
    await page.goto("/recommend");

    const width = testInfo.project.use.viewport?.width ?? 0;

    if (width < 768) {
      await expect(page.getByTestId("tabbar-bar")).toBeVisible();
      await expect(page.getByTestId("tabbar-rail")).toBeHidden();
      await expect(page.getByTestId("tabbar-sidebar")).toBeHidden();
    } else if (width < 1024) {
      await expect(page.getByTestId("tabbar-bar")).toBeHidden();
      await expect(page.getByTestId("tabbar-rail")).toBeVisible();
      await expect(page.getByTestId("tabbar-sidebar")).toBeHidden();
    } else {
      await expect(page.getByTestId("tabbar-bar")).toBeHidden();
      await expect(page.getByTestId("tabbar-rail")).toBeHidden();
      await expect(page.getByTestId("tabbar-sidebar")).toBeVisible();
    }

    const nav = page.getByRole("navigation", { name: "Primary" });
    for (const label of DESTINATIONS) {
      await expect(nav.getByRole("link", { name: label, exact: false }).first()).toBeVisible();
    }
  });

  test("Create is never a fifth nav destination", async ({ page }) => {
    // Create legitimately renders inside the nav chrome (positioned per tier,
    // spec.md FR-003) — the requirement is that it's never treated as one of
    // the four destinations: it must never carry aria-current, regardless of
    // the current route.
    await page.goto("/add");
    const nav = page.getByRole("navigation", { name: "Primary" });
    await expect(nav.locator('[aria-current="page"][href="/add"]')).toHaveCount(0);
  });
});

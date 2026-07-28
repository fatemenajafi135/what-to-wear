import { test, expect } from "@playwright/test";

test('"/" redirects to /recommend (spec.md FR-015)', async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/recommend$/);
});

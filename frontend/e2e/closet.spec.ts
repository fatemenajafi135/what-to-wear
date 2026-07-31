import { test, expect } from "@playwright/test";

/**
 * specs/004-closet-read/spec.md User Story 4 (FR-005): a brand-new,
 * zero-item closet shows the first-run empty state, never empty-filtered.
 * Follows auth-flow.spec.ts's established pattern (sign up a fresh user
 * inline) since no wardrobe-item seeding path exists yet for e2e — feature
 * 005 (closet write) is what adds one. Populated-grid, filter, item-detail
 * and error/offline states are covered by manual browser verification
 * (see the feature's implementation report) rather than here, since seeding
 * real rows for a fresh e2e user has no established pattern in this suite
 * yet; a named gap, not an oversight.
 */
test("brand-new user sees the first-run empty closet, not empty-filtered", async ({ page }) => {
  const email = `closet-e2e-${Date.now()}@example.com`;
  const password = "longenoughpassword";

  await page.goto("/signup");
  await page.waitForLoadState("networkidle");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/recommend$/, { timeout: 15000 });

  await page.goto("/closet");
  await expect(page.getByRole("heading", { name: "Closet" })).toBeVisible();
  await expect(page.getByText("0 items")).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Your closet is empty. Add a few pieces and I'll start suggesting outfits.")).toBeVisible();
  await expect(page.getByText("No items match this filter.")).not.toBeVisible();

  for (const chip of ["All", "Tops", "Bottoms", "Outerwear", "Shoes", "Accessories"]) {
    await expect(page.getByRole("button", { name: chip, exact: true })).toBeVisible();
  }

  await page.getByRole("link", { name: "Add your first item" }).click();
  await expect(page).toHaveURL(/\/add$/);
});

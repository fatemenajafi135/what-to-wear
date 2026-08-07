import { test, expect } from "@playwright/test";

/**
 * spec.md FR-010/FR-011/FR-013 (US5). Needs a running local Supabase
 * (research.md §5) — signs up a fresh throwaway account via the UI to
 * exercise a real signed-in session rather than fabricating one.
 */
test("signed-out visitors are redirected away from an authenticated route", async ({ page }) => {
  await page.goto("/recommend");
  await expect(page).toHaveURL(/\/signin$/);
});

test("signed-in visitors are redirected away from an auth route, and sign-out returns them to /signin", async ({
  page,
}) => {
  const email = `route-protection-${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("longenoughpassword");
  await page.getByLabel("Confirm password").fill("longenoughpassword");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/recommend$/);

  await page.goto("/signin");
  await expect(page).toHaveURL(/\/recommend$/);

  await page.goto("/profile");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/signin$/);

  await page.goto("/recommend");
  await expect(page).toHaveURL(/\/signin$/);
});

import { test, expect } from "@playwright/test";

/**
 * spec.md FR-012: "/" redirects by auth state, replacing feature 001's
 * unconditional redirect(). Needs a running local Supabase (research.md
 * §5) — the signed-in case signs up a fresh throwaway account via the UI
 * rather than faking a session, since PKCE/cookie state isn't something a
 * test can fabricate without going through the real flow at least once.
 */
test('"/" redirects to /signin when signed out', async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/signin$/);
});

test('"/" redirects to /recommend when signed in', async ({ page }) => {
  const email = `root-redirect-${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("longenoughpassword");
  await page.getByLabel("Confirm password").fill("longenoughpassword");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/recommend$/);

  await page.goto("/");
  await expect(page).toHaveURL(/\/recommend$/);
});

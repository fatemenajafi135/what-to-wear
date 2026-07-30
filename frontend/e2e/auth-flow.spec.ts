import { test, expect } from "@playwright/test";

/**
 * spec.md handoff §10's core Definition-of-Done scenario: sign up → sign
 * out → sign in → sign out, plus FR-009/SC-004 (session survives a
 * reload). Needs a running local Supabase (research.md §5).
 */
test("sign up, sign out, sign in, sign out — with a reload in between proving session persistence", async ({
  page,
}) => {
  const email = `auth-flow-${Date.now()}@example.com`;
  const password = "longenoughpassword";

  await page.goto("/signup");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/recommend$/);

  // FR-009/SC-004: reload keeps the session — no bounce to /signin.
  await page.reload();
  await expect(page).toHaveURL(/\/recommend$/);

  await page.goto("/profile");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/signin$/);

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/recommend$/);

  await page.goto("/profile");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/signin$/);
});

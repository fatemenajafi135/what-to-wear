import { test, expect } from "@playwright/test";

const MAILPIT_URL = "http://127.0.0.1:54324";

/**
 * spec.md US3 / SC-005. Needs a running local Supabase (research.md §5) —
 * fetches the real recovery email from Mailpit's local capture server
 * rather than mocking it, since the whole point is proving the emailed
 * /reset-password/:token link (research.md §6) actually works.
 */
async function latestResetLinkFor(email: string): Promise<string> {
  const search = await fetch(`${MAILPIT_URL}/api/v1/search?query=to:${email}`);
  const { messages } = await search.json();
  const latest = messages[0];
  const full = await fetch(`${MAILPIT_URL}/api/v1/message/${latest.ID}`);
  const { HTML } = await full.json();
  const match = HTML.match(/href="([^"]*\/reset-password\/[^"]+)"/);
  if (!match) throw new Error("No reset-password link found in the captured email");
  return match[1];
}

test("requesting, following, and completing a password reset invalidates the old password", async ({ page }) => {
  const email = `password-reset-${Date.now()}@example.com`;
  const oldPassword = "originalpassword1";
  const newPassword = "brandnewpassword2";

  await page.goto("/signup");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(oldPassword);
  await page.getByLabel("Confirm password").fill(oldPassword);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/recommend$/);

  await page.goto("/profile");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/signin$/);

  await page.goto("/forgot-password");
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByText(email, { exact: false })).toBeVisible();

  const resetLink = await latestResetLinkFor(email);
  await page.goto(resetLink);
  await expect(page.getByLabel("New password")).toBeVisible();
  await page.getByLabel("New password").fill(newPassword);
  await page.getByLabel("Confirm password").fill(newPassword);
  await page.getByRole("button", { name: "Update password" }).click();

  // FR-008: lands on the success state's own "Sign in" link, not signed in.
  await page.getByRole("link", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/signin$/);

  // SC-005, second half: the old password no longer works.
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(oldPassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("That email and password don't match. Try again or reset your password.")).toBeVisible();

  // SC-005, first half: the new password works.
  await page.getByLabel("Password").fill(newPassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/recommend$/);
});

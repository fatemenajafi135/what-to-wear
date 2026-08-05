import { test, expect } from "@playwright/test";
import { forceNavigatorOffline, signUpFreshUser } from "./helpers";

/**
 * User Story 1 (spec.md) — three acceptance scenarios. Every case needs the
 * app already loaded once online first: a brand-new visitor's very first,
 * ever offline load is an accepted exception (spec.md Edge Cases — "nothing
 * to precache yet").
 */
test.describe("offline cold start renders the app shell, not a browser error", () => {
  test("a full offline reload renders the app shell with the offline banner", async ({ page, context }) => {
    await signUpFreshUser(page, "offline1");
    await page.goto("/recommend");
    await page.waitForLoadState("networkidle");

    await context.setOffline(true);
    await forceNavigatorOffline(page);
    await page.reload();

    // Not the <nav> landmark itself: its only children are `position: fixed`
    // (TabBar.module.css), so it collapses to zero own height in normal
    // flow (correct, expected CSS — fixed children never contribute to a
    // parent's box) and Playwright's toBeVisible() reports it as hidden even
    // though its content renders on screen. A visible child link is the
    // real assertion.
    await expect(page.getByRole("link", { name: "Recommend" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("You're offline. Some actions are unavailable until you're reconnected.")).toBeVisible();
  });

  test("a previously-visited screen still shows its last-known data while offline", async ({ page, context }) => {
    await signUpFreshUser(page, "offline2");
    await page.goto("/closet");
    await expect(page.getByRole("heading", { name: "Closet" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("0 items")).toBeVisible({ timeout: 15000 });
    await page.waitForLoadState("networkidle");

    await context.setOffline(true);
    await forceNavigatorOffline(page);
    await page.reload();

    // Cached data (the "0 items" empty state itself is real, cached data —
    // not a network failure) renders, with the offline banner layered on top.
    await expect(page.getByRole("heading", { name: "Closet" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("0 items")).toBeVisible();
    await expect(page.getByText("You're offline. Some actions are unavailable until you're reconnected.")).toBeVisible();
  });

  test("a screen never fetched this session shows its own empty/error state offline, not a raw network error", async ({
    page,
    context,
  }) => {
    await signUpFreshUser(page, "offline3");
    await page.goto("/recommend");
    await page.waitForLoadState("networkidle");

    await context.setOffline(true);
    // Client-side navigation (a TabBar link), not page.goto: this tests the
    // screen's own DATA fetch failing while offline, not whether the
    // document/RSC payload for a never-visited *route* was precached — a
    // different, out-of-scope question (spec.md Edge Cases accepts a raw
    // browser error only for a route never loaded at all).
    await page.getByRole("link", { name: "Outfits" }).click();

    // Not the <nav> landmark itself: its only children are `position: fixed`
    // (TabBar.module.css), so it collapses to zero own height in normal
    // flow (correct, expected CSS — fixed children never contribute to a
    // parent's box) and Playwright's toBeVisible() reports it as hidden even
    // though its content renders on screen. A visible child link is the
    // real assertion.
    await expect(page.getByRole("link", { name: "Recommend" })).toBeVisible({ timeout: 15000 });
    const bodyText = await page.textContent("body");
    expect(bodyText?.toLowerCase()).not.toMatch(/queued|retry automatically|sync once|once you.?re back/);
  });
});

import { test, expect } from "@playwright/test";
import { API_DATA_CACHE, PHOTOS_CACHE } from "../lib/serviceWorker/cacheNames";
import {
  API_ORIGIN,
  STORAGE_ORIGIN,
  ONE_PIXEL_PNG,
  cacheKeys,
  forceNavigatorOffline,
  mockOneClosetItemWithPhoto,
  signOutViaUi,
  signUpFreshUser,
} from "./helpers";

/**
 * User Story 2 (spec.md) — the privacy-critical purge. Both acceptance
 * scenarios in one flow: sign-out clears the two user-scoped caches, and a
 * second user on the same browser profile sees none of the first user's
 * data, even offline.
 */
test.describe("sign-out purges every cache that could hold the previous user's data", () => {
  test("sign-out deletes wtw-api-data and wtw-photos, and a second user never sees the first user's data offline", async ({
    page,
    context,
  }) => {
    await mockOneClosetItemWithPhoto(page, {
      itemName: "User A's private jacket",
      photoUrl: `${STORAGE_ORIGIN}/storage/v1/object/sign/wardrobe-photos/user-a/fake-item-1.jpg?token=a`,
    });
    await page.context().route(`${STORAGE_ORIGIN}/storage/v1/object/sign/wardrobe-photos/**`, async (route) => {
      await route.fulfill({ status: 200, contentType: "image/png", body: ONE_PIXEL_PNG });
    });

    const userA = await signUpFreshUser(page, "purge-a");
    await page.goto("/closet");
    await expect(page.getByRole("link", { name: "User A's private jacket" })).toBeVisible({ timeout: 30000 });
    await page.waitForLoadState("networkidle");

    await expect
      .poll(() => cacheKeys(page), { timeout: 15000 })
      .toEqual(expect.arrayContaining([API_DATA_CACHE, PHOTOS_CACHE]));

    await signOutViaUi(page);

    // Purged entirely — not present-but-empty, the cache name itself is gone.
    await expect.poll(() => cacheKeys(page), { timeout: 15000 }).not.toEqual(
      expect.arrayContaining([API_DATA_CACHE]),
    );
    const keysAfterSignOut = await cacheKeys(page);
    expect(keysAfterSignOut).not.toContain(API_DATA_CACHE);
    expect(keysAfterSignOut).not.toContain(PHOTOS_CACHE);
    // The app-shell precache is untouched — no user data in it (research.md R1).
    expect(keysAfterSignOut.some((k) => k.includes("precache"))).toBe(true);

    // A second, unrelated user signs up on the same browser profile — real
    // data this time (unroute the mock), so any leak would be user A's
    // actual mocked item name showing up where it has no business being.
    await page.context().unroute(`${API_ORIGIN}/api/v1/closet/items*`);
    const userB = await signUpFreshUser(page, "purge-b");
    await forceNavigatorOffline(page);
    await context.setOffline(true);
    await page.goto("/closet");

    await expect(page.getByRole("link", { name: "Recommend" })).toBeVisible({ timeout: 15000 });
    const bodyText = await page.textContent("body");
    expect(bodyText).not.toContain("User A's private jacket");

    void userA;
    void userB;
  });
});

import { test, expect } from "@playwright/test";
import { API_DATA_CACHE, PHOTOS_CACHE } from "../lib/serviceWorker/cacheNames";
import {
  STORAGE_ORIGIN,
  ONE_PIXEL_PNG,
  cacheKeys,
  mockOneClosetItemWithPhoto,
  signUpFreshUser,
} from "./helpers";

/**
 * Foundational proof (tasks.md T009): the service worker actually registers
 * and reaches `activated`, and the full route table (contracts/route-caching.md)
 * is live — every user story's own spec builds on this being true.
 */
test.describe("service worker registers and the route table is live", () => {
  test("a built app registers an activated service worker that controls the page", async ({ page }) => {
    // Deliberately pre-auth (/signin): the SW must register here too, not
    // only once signed in — this is what caught proxy.ts redirecting /sw.js
    // itself to /signin (a real bug in this codebase, fixed alongside this
    // test — browsers refuse to install a service worker whose script
    // response is a redirect).
    await page.goto("/signin");
    await page.waitForFunction(async () => {
      const registration = await navigator.serviceWorker.getRegistration();
      return registration?.active?.state === "activated";
    }, { timeout: 15000 });

    await expect
      .poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null), { timeout: 15000 })
      .toBe(true);
  });

  test("the app-shell precache, API-data cache, and photos cache all appear", async ({ page }) => {
    // Mocked at the browser-CONTEXT level, not the page level: the actual
    // network fetch for a NetworkFirst/CacheFirst cache miss is issued from
    // inside the service worker's own execution context, which page.route()
    // does not see — only context.route() reaches it (found empirically
    // while writing this test; page.route() left the request unmocked and
    // the closet screen rendered the real signed-up user's real "0 items").
    await mockOneClosetItemWithPhoto(page, {
      itemName: "Smoke test jacket",
      photoUrl: `${STORAGE_ORIGIN}/storage/v1/object/sign/wardrobe-photos/test-user/fake-item-1.jpg?token=smoke`,
    });
    await page.context().route(`${STORAGE_ORIGIN}/storage/v1/object/sign/wardrobe-photos/**`, async (route) => {
      await route.fulfill({ status: 200, contentType: "image/png", body: ONE_PIXEL_PNG });
    });

    await signUpFreshUser(page, "smoke");
    await page.goto("/closet");
    // Real sign-up (Supabase) + first compile of a route can be slow in this
    // environment — generous timeout, this isn't testing UI responsiveness.
    // A role locator, not getByText: the tile's title renders inside nested
    // elements and getByText proved flaky against it in practice, while the
    // link's accessible name is exactly the item name.
    await expect(page.getByRole("link", { name: "Smoke test jacket" })).toBeVisible({ timeout: 30000 });
    // The item tile's <img> firing is what makes the SW actually intercept
    // and cache the signed-photo request (class 4) — wait for it to load.
    await page.waitForLoadState("networkidle");

    await expect
      .poll(() => cacheKeys(page), { timeout: 15000 })
      .toEqual(expect.arrayContaining([API_DATA_CACHE, PHOTOS_CACHE]));
    const keys = await cacheKeys(page);
    expect(keys.some((k) => k.includes("precache"))).toBe(true);
  });
});

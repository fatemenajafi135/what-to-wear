import { test, expect } from "@playwright/test";
import { PHOTOS_CACHE } from "../lib/serviceWorker/cacheNames";
import {
  ONE_PIXEL_PNG,
  STORAGE_ORIGIN,
  ensureServiceWorkerControlling,
  mockOneClosetItemWithPhoto,
  signUpFreshUser,
} from "./helpers";

/**
 * Regression for the defect found in review (docs/design-decisions.md §52):
 * `ItemPhoto`'s <img> had no `crossorigin` attribute, so every request to
 * Supabase Storage — success or failure — was opaque (`status 0`).
 * `CacheableResponsePlugin({ statuses: [0, 200] })` therefore could not tell
 * a real photo from a transient failure apart, and cached the failure. A
 * photo that failed once with a 500 then stayed broken — rendering the
 * NoPhoto placeholder from a cached failure, with **zero** further network
 * requests — for up to `wtw_photo_signed_url_ttl_seconds` (an hour), even
 * though the same signed URL was perfectly valid on every later request.
 *
 * Fix: `crossOrigin="anonymous"` on the <img> (Supabase Storage sends
 * `Access-Control-Allow-Origin: *`, including on error responses — verified)
 * makes the response a real, readable one, and `app/sw.ts`'s photo rule is
 * tightened to `statuses: [200]` only, so the plugin can actually see and
 * reject a 500.
 */
async function photosCacheEntries(page: import("@playwright/test").Page) {
  return page.evaluate(async (name) => {
    // Not `caches.has()` first: `open()` is idempotent (creates-or-opens),
    // so there is no reason to guard it, and an empty result already means
    // "no entries" whether or not the cache technically exists yet.
    const cache = await caches.open(name);
    const keys = await cache.keys();
    return Promise.all(
      keys.map(async (k) => {
        const res = await cache.match(k);
        return { url: k.url, status: res?.status, type: res?.type };
      }),
    );
  }, PHOTOS_CACHE);
}

test("a photo that fails once recovers on the next request, rather than staying broken from a cached failure", async ({
  page,
}) => {
  let photoRequestCount = 0;
  const photoUrl = `${STORAGE_ORIGIN}/storage/v1/object/sign/wardrobe-photos/test-user/flaky.jpg?token=flaky`;

  await mockOneClosetItemWithPhoto(page, { itemName: "Flaky photo item", photoUrl });
  await page.context().route(`${STORAGE_ORIGIN}/storage/v1/object/sign/wardrobe-photos/**`, async (route) => {
    photoRequestCount += 1;
    if (photoRequestCount === 1) {
      await route.fulfill({ status: 500, contentType: "text/plain", body: "internal error" });
      return;
    }
    await route.fulfill({ status: 200, contentType: "image/png", body: ONE_PIXEL_PNG });
  });

  await signUpFreshUser(page, "photo-recovery");
  await page.goto("/closet");
  // Cache assertions below are only meaningful once the worker actually
  // controls this page — an uncontrolled fetch bypasses it entirely with no
  // error (helpers.ts's own comment on why this is needed).
  await ensureServiceWorkerControlling(page);
  const tile = page.getByRole("link", { name: "Flaky photo item" });
  await expect(tile).toBeVisible({ timeout: 30000 });

  // First load: the 500 fails, NoPhoto renders — expected, not the bug.
  await expect(tile.locator("img")).toHaveCount(0, { timeout: 15000 });
  await expect.poll(() => photoRequestCount, { timeout: 15000 }).toBe(1);

  // The bug is what gets written to Cache Storage in the background
  // (`event.waitUntil`, not synchronous with the fetch response) — poll
  // rather than check once immediately after the request resolves.
  // Un-fixed: one opaque (status 0) entry, the failure cached as if it were
  // a photo. Fixed: no entry at all — a 500 is correctly rejected.
  await page.waitForTimeout(1000);
  const entriesAfterFailure = await photosCacheEntries(page);
  console.log("wtw-photos after the failing load:", JSON.stringify(entriesAfterFailure));

  // A cached *failure* would mean this reload makes ZERO further network
  // requests and stays on NoPhoto forever — the exact bug found in review.
  // A real fix means a second request goes out and the photo recovers.
  await page.reload();
  const tileAfterReload = page.getByRole("link", { name: "Flaky photo item" });
  await expect(tileAfterReload).toBeVisible({ timeout: 15000 });
  await expect(tileAfterReload.locator("img")).toHaveCount(1, { timeout: 15000 });
  await expect.poll(() => photoRequestCount, { timeout: 15000 }).toBeGreaterThan(1);

  // And the healthy response is now the one actually cached — status 200,
  // not the earlier opaque failure.
  await page.waitForTimeout(1000);
  const entriesAfterRecovery = await photosCacheEntries(page);
  console.log("wtw-photos after recovery:", JSON.stringify(entriesAfterRecovery));
  expect(entriesAfterRecovery.some((e) => e.status === 200)).toBe(true);
  expect(entriesAfterRecovery.some((e) => e.status === 0)).toBe(false);
});

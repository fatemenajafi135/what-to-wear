import { test, expect } from "@playwright/test";
import { STORAGE_ORIGIN, mockOneClosetItemWithPhoto, signUpFreshUser } from "./helpers";

/**
 * User Story 3 (spec.md) — an expired signed photo URL never renders a
 * browken-image icon. Mocked at the browser-context level (`research.md`
 * R9's reasoning extended to fixture data): the backend's actual signed-URL
 * expiry is a 3600s window, far too slow to exercise directly in a test, so
 * a 400 response from Storage stands in for "the token has expired" — the
 * client has no way to distinguish the two anyway (docs/design-decisions.md
 * §52's ItemPhoto section).
 */
test.describe("an expired signed photo URL never renders as a broken image", () => {
  test("a 400 from Storage falls back to the NoPhoto placeholder, not a broken image", async ({ page }) => {
    await mockOneClosetItemWithPhoto(page, {
      itemName: "Item with an expired photo",
      photoUrl: `${STORAGE_ORIGIN}/storage/v1/object/sign/wardrobe-photos/test-user/expired.jpg?token=expired`,
    });
    await page.context().route(`${STORAGE_ORIGIN}/storage/v1/object/sign/wardrobe-photos/**`, async (route) => {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ statusCode: "400", error: "invalid_token" }),
      });
    });

    await signUpFreshUser(page, "expiredphoto");
    await page.goto("/closet");
    await expect(page.getByRole("link", { name: "Item with an expired photo" })).toBeVisible({ timeout: 30000 });

    // No <img> anywhere in the tile once the load fails — the placeholder
    // (NoPhoto's aria-hidden "image-off" glyph) takes over instead
    // (ItemPhoto.tsx onError -> NoPhoto). .first(): both NoPhoto's own
    // wrapper div and its inner icon carry aria-hidden="true".
    const tile = page.getByRole("link", { name: "Item with an expired photo" });
    await expect(tile.locator("img")).toHaveCount(0, { timeout: 15000 });
    await expect(tile.locator('[aria-hidden="true"]').first()).toBeVisible();
  });

  test("back online with a fresh signed URL, the real photo renders normally", async ({ page }) => {
    await mockOneClosetItemWithPhoto(page, {
      itemName: "Item with a working photo",
      photoUrl: `${STORAGE_ORIGIN}/storage/v1/object/sign/wardrobe-photos/test-user/working.jpg?token=fresh`,
    });
    await page.context().route(`${STORAGE_ORIGIN}/storage/v1/object/sign/wardrobe-photos/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "image/png",
        // 1x1 png, inline to avoid a second fixture import for one assertion.
        body: Buffer.from(
          "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
          "base64",
        ),
      });
    });

    await signUpFreshUser(page, "workingphoto");
    await page.goto("/closet");
    const tile = page.getByRole("link", { name: "Item with a working photo" });
    await expect(tile).toBeVisible({ timeout: 30000 });
    const img = tile.locator("img");
    await expect(img).toHaveCount(1, { timeout: 15000 });
    await expect(img).toHaveAttribute("src", /working\.jpg/);
  });
});

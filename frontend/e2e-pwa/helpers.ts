import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

/**
 * Local-dev origins the built app talks to — matches `.env.local`
 * (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`), the same values
 * `app/sw.ts` reads at build time. Hardcoded here (Playwright's Node
 * process doesn't load Next's `.env.local`) rather than re-derived, since
 * this whole suite already only runs against the fixed local stack
 * (`playwright.pwa.config.ts` builds+starts on a fixed port for the same
 * reason).
 */
export const API_ORIGIN = "http://localhost:8000";
export const STORAGE_ORIGIN = "http://127.0.0.1:54321";

/**
 * Signs up a brand-new user inline, same pattern as the existing dev-server
 * suite's `e2e/closet.spec.ts` and `e2e/auth-flow.spec.ts` — no seeded
 * fixture user exists for either suite, by design (no established seeding
 * path predates this feature).
 */
export async function signUpFreshUser(page: Page, label: string): Promise<{ email: string; password: string }> {
  const email = `pwa-e2e-${label}-${Date.now()}@example.com`;
  const password = "longenoughpassword";

  await page.goto("/signup");
  await page.waitForLoadState("networkidle");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/recommend$/, { timeout: 15000 });

  return { email, password };
}

export async function signInExistingUser(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/signin");
  await page.waitForLoadState("networkidle");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/recommend$/, { timeout: 15000 });
}

export async function signOutViaUi(page: Page): Promise<void> {
  await page.goto("/profile");
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/signin$/, { timeout: 15000 });
}

/** All Cache Storage names currently present, from the page's own origin. */
export async function cacheKeys(page: Page): Promise<string[]> {
  return page.evaluate(() => caches.keys());
}

/**
 * A minimal but schema-valid `ClosetItemView` (backend/src/whattowear/api/v1/routes/closet.py).
 * `photoUrl` is intentionally the only thing callers usually vary.
 */
export function fakeClosetItem(overrides: { id: string; name: string; photoUrl: string | null }) {
  return {
    id: overrides.id,
    category: "top",
    category_group: "top",
    colors: ["#1b2a4a"],
    color_names: ["navy"],
    formality: "casual",
    warmth: 2,
    season: ["all"],
    fabric: null,
    source: "upload",
    pattern: null,
    fit: null,
    photo_path: `test-user/${overrides.id}.jpg`,
    photo_background_color: null,
    name: overrides.name,
    notes: null,
    favorite: false,
    photo_url: overrides.photoUrl,
  };
}

/**
 * Intercepts `GET {API_ORIGIN}/api/v1/closet/items*` and returns exactly one
 * fake item — avoids depending on real vision extraction (a live, billed LLM
 * call) just to get a photo-bearing item into the app for a cache-behavior
 * test, mirroring the Quality Bar's "CI must not make live LLM calls" rule
 * in spirit (research.md R9's reasoning, extended to this fixture data).
 *
 * Routed via `page.context()`, not `page` itself: with the service worker
 * active and controlling the page, a `NetworkFirst`/`CacheFirst` cache miss
 * is fetched from inside the SW's own execution context, which `page.route()`
 * never sees (confirmed empirically — it left the request to reach the real
 * backend). `context.route()` is what actually reaches it.
 */
export async function mockOneClosetItemWithPhoto(
  page: Page,
  options: { itemName: string; photoUrl: string | null },
): Promise<void> {
  await page.context().route(`${API_ORIGIN}/api/v1/closet/items*`, async (route) => {
    const item = fakeClosetItem({ id: "fake-item-1", name: options.itemName, photoUrl: options.photoUrl });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [item], total: 1, has_more: false }),
    });
  });
}

/** A tiny valid PNG (1x1, transparent) — enough for a real `<img>` load to succeed. */
export const ONE_PIXEL_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

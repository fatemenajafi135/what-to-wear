import type { Page } from "@playwright/test";
import { DEV_CATALOG_BASE_URL } from "../playwright.config";

/**
 * The dev-only catalog is only reachable via `next dev` (spec.md FR-005a
 * 404s it in production). Turbopack's dev client finishes an HMR
 * reconciliation pass shortly after the initial load, which can otherwise
 * race with an immediate click (e.g. showModal() firing just before a
 * remount clears the native <dialog>'s open state) — waiting for the page
 * to go network-idle avoids that race.
 */
export async function gotoCatalog(page: Page): Promise<void> {
  await page.goto(`${DEV_CATALOG_BASE_URL}/dev/components`);
  await page.waitForLoadState("networkidle");
}

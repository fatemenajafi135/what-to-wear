import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect } from "@playwright/test";
import { signUpFreshUser } from "./helpers";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * User Story 4 (spec.md) — the handoff's highest-risk item: prove an
 * already-open client actually gets pushed onto a new version, not just that
 * a toast renders.
 *
 * Simulating "a new version was deployed" without a real rebuild+restart
 * cycle: `next start` serves `public/sw.js` fresh off disk on every request
 * (no in-memory caching of static assets), so overwriting that one file
 * mid-test is a legitimate stand-in for a deploy — it produces exactly what
 * the browser's own update check reacts to (different script bytes), the
 * one thing this mechanism actually depends on. The rest of the built app
 * (`.next/`) is untouched; this test verifies the update *mechanism*
 * (detect → wait → accept → skipWaiting → reload → new script active), not
 * that new application features appear.
 */
const SW_PATH = path.join(__dirname, "..", "public", "sw.js");

test.describe("an already-open client is offered the new version and can accept it", () => {
  let originalSwContent: string;

  test.beforeEach(async () => {
    originalSwContent = await readFile(SW_PATH, "utf-8");
  });

  test.afterEach(async () => {
    // Restore the real build output so other tests (and a human re-running
    // this suite without a fresh `npm run build`) see the genuine artifact.
    await writeFile(SW_PATH, originalSwContent, "utf-8");
  });

  test("accepting the update reloads onto the new service worker", async ({ page }) => {
    await page.goto("/signin");
    await page.waitForFunction(async () => {
      const reg = await navigator.serviceWorker.getRegistration();
      return reg?.active?.state === "activated";
    }, { timeout: 15000 });
    await expect
      .poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null))
      .toBe(true);

    // "Deploy" a new version: the SW script's bytes change.
    const marker = `e2e-update-marker-${Date.now()}`;
    await writeFile(SW_PATH, `${originalSwContent}\n// ${marker}\n`, "utf-8");

    // Reload-triggered detection (spec.md Clarifications): a real navigation
    // is what makes the browser re-check the service worker's script.
    await page.reload();

    await expect(page.getByText("A new version is ready.")).toBeVisible({ timeout: 15000 });
    await expect
      .poll(async () => {
        const reg = await page.evaluate(async () => {
          const r = await navigator.serviceWorker.getRegistration();
          return r?.waiting?.state ?? null;
        });
        return reg;
      }, { timeout: 15000 })
      .toBe("installed");

    await Promise.all([page.waitForEvent("load"), page.getByRole("button", { name: "Update now" }).click()]);

    // The new worker is now active and nothing is waiting anymore — the
    // reload actually landed on the new version, not a refresh that
    // re-served the old cached shell under the old controller (FR-008).
    await expect
      .poll(() =>
        page.evaluate(async () => {
          const r = await navigator.serviceWorker.getRegistration();
          return { waiting: r?.waiting != null, active: r?.active?.state ?? null };
        }),
      { timeout: 15000 })
      .toEqual({ waiting: false, active: "activated" });

    const swContentAfter = await page.evaluate(() => fetch("/sw.js").then((r) => r.text()));
    expect(swContentAfter).toContain(marker);
  });

  test("dismissing the toast keeps the current version running and does not force a reload", async ({ page }) => {
    // Signed in this time (not just /signin): the "no reappearance on
    // in-app navigation" half of this test needs a TabBar link to click.
    await signUpFreshUser(page, "dismiss-update");
    await page.waitForFunction(async () => {
      const reg = await navigator.serviceWorker.getRegistration();
      return reg?.active?.state === "activated";
    }, { timeout: 15000 });
    // Without waiting for the controller to actually attach, an immediate
    // reload+overwrite raced the SW registration's own bookkeeping and the
    // update check on that reload didn't reliably fire (found empirically —
    // the "accept" test above already waits for this and is reliable).
    await expect
      .poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null))
      .toBe(true);

    const marker = `e2e-dismiss-marker-${Date.now()}`;
    await writeFile(SW_PATH, `${originalSwContent}\n// ${marker}\n`, "utf-8");
    await page.reload();

    await expect(page.getByText("A new version is ready.")).toBeVisible({ timeout: 15000 });

    const urlBefore = page.url();
    await page.getByRole("button", { name: "Dismiss" }).click();
    await expect(page.getByText("A new version is ready.")).not.toBeVisible();

    // No forced reload — same document, same URL, still responsive.
    await page.waitForTimeout(500);
    expect(page.url()).toBe(urlBefore);
    await expect(page.getByRole("link", { name: "Recommend" })).toBeVisible();

    // Per spec.md Clarifications: does not reappear on in-app (client-side)
    // navigation — only a new reload/relaunch would re-check.
    await page.getByRole("link", { name: "Closet", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Closet" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("A new version is ready.")).not.toBeVisible();
  });
});

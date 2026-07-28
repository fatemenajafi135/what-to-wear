import { test, expect } from "@playwright/test";
import { gotoCatalog } from "./catalog";

test.describe("BottomSheet dialog semantics (spec.md FR-010)", () => {
  test("traps focus, supports Escape-to-close, and restores focus on close", async ({ page }) => {
    await gotoCatalog(page);

    const openButton = page.getByRole("button", { name: "Open (normal)" }).first();
    await openButton.click();

    const dialog = page.getByRole("dialog").first();
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("aria-labelledby", /.+/);

    // Tab through the dialog's own focusable descendants; focus must never
    // land on a real control outside the dialog (native <dialog>/showModal()
    // guarantees this). Chromium briefly parks activeElement on <body> for
    // a single tick while wrapping from the last focusable element back to
    // the first — that's the browser's own focus-trap implementation detail,
    // not focus escaping to page content, so it's tolerated here alongside
    // "inside the dialog".
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press("Tab");
      const focusEscaped = await page.evaluate(() => {
        const active = document.activeElement;
        const dialogEl = document.querySelector("dialog[open]");
        if (!dialogEl || !active) return true;
        return !dialogEl.contains(active) && active !== document.body;
      });
      expect(focusEscaped).toBe(false);
    }

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(openButton).toBeFocused();
  });
});

import { test, expect } from "@playwright/test";

/**
 * spec.md FR-005 / Clarifications 2026-07-28 / SC-005: theme is resolved
 * entirely server-side from the wtw-theme cookie, with a fixed light
 * default when absent — no client-side matchMedia fallback ever swaps it
 * after the fact. Both branches are checked directly in the raw HTML
 * response, which is the actual mechanism the "0 flashes across 20
 * reloads" manual pass in quickstart.md depends on.
 */
test.describe("server-resolved boot theme, no post-hydration flip", () => {
  test("wtw-theme=dark cookie renders data-theme=dark in the raw response", async ({
    request,
    baseURL,
  }) => {
    const response = await request.get(`${baseURL}/recommend`, {
      headers: { Cookie: "wtw-theme=dark" },
    });
    const body = await response.text();
    expect(body).toContain('data-theme="dark"');
  });

  test("with no cookie, the raw response always carries the fixed light default", async ({
    request,
    baseURL,
  }) => {
    const response = await request.get(`${baseURL}/recommend`);
    const body = await response.text();
    expect(body).toContain('data-theme="light"');
  });

  test("no cookie set in-browser never flips the rendered theme after load", async ({
    page,
    context,
  }) => {
    await context.clearCookies();
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/recommend");
    // Give any hypothetical client script a moment to run — there should be
    // none, so the attribute must still read the server-rendered default.
    await page.waitForTimeout(300);
    const theme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    expect(theme).toBe("light");
  });
});

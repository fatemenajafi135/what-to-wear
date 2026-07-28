import { test, expect } from "@playwright/test";

test.describe("PWA manifest (spec.md FR-012, contracts/manifest.md)", () => {
  test("manifest.webmanifest matches the contract, including real shortcut routes", async ({
    request,
    baseURL,
  }) => {
    const response = await request.get(`${baseURL}/manifest.webmanifest`);
    expect(response.ok()).toBe(true);
    const manifest = await response.json();

    expect(manifest.name).toBe("What to Wear");
    expect(manifest.short_name).toBe("What to Wear");
    expect(manifest.display).toBe("standalone");
    expect(manifest.start_url).toBe("/?source=pwa");
    expect(manifest.background_color).toBe("#E6E1D6");
    expect(manifest.theme_color).toBe("#4B2E52");

    expect(manifest.icons).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ src: "/icons/icon-192.png", sizes: "192x192" }),
        expect.objectContaining({ src: "/icons/icon-512.png", sizes: "512x512" }),
        expect.objectContaining({ purpose: "maskable" }),
      ]),
    );

    const shortcutUrls = manifest.shortcuts.map((s: { url: string }) => s.url);
    expect(shortcutUrls).toEqual(expect.arrayContaining(["/add", "/recommend"]));
  });

  test("both light/dark theme-color meta tags are present", async ({ page }) => {
    await page.goto("/recommend");
    const light = page.locator('meta[name="theme-color"][media="(prefers-color-scheme: light)"]');
    const dark = page.locator('meta[name="theme-color"][media="(prefers-color-scheme: dark)"]');
    await expect(light).toHaveAttribute("content", "#E6E1D6");
    await expect(dark).toHaveAttribute("content", "#1C1822");
  });
});

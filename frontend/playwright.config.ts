import { defineConfig, devices } from "@playwright/test";

const PORT = 3100;
// The dev-only component catalog (spec.md FR-005a) 404s under
// NODE_ENV=production by design (research.md "Dev-only catalog route
// gating"), so the whole suite runs against `next dev` — none of these
// assertions (chrome/focus/manifest/theme/redirect/a11y) depend on
// production-only behavior. Production-build verification (Lighthouse
// installability) is a separate manual check, not part of this suite.
export const DEV_CATALOG_BASE_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  timeout: 30_000,
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  webServer: {
    command: `npm run dev -- -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: "mobile-320",
      use: { ...devices["Desktop Chrome"], viewport: { width: 320, height: 800 } },
    },
    {
      name: "tablet-768",
      use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 } },
    },
    {
      name: "desktop-1024",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1024, height: 900 } },
    },
    {
      name: "desktop-1440",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 960 } },
    },
  ],
});

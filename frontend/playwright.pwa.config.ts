import { defineConfig, devices } from "@playwright/test";

/**
 * Serwist disables service-worker registration under `next dev`
 * (next.config.ts, research.md R9) — everything this config exercises
 * (precaching, offline navigation, sign-out cache purge, the update/
 * skip-waiting round trip) is only observable against a real production
 * build. Kept separate from `playwright.config.ts` (which runs `next dev`
 * for fast iteration on everything else) so the default `npm run e2e` loop
 * isn't slowed down by a full build on every run — this suite runs via
 * `npm run e2e:pwa` on demand and in CI.
 */
// Port 3100, not a fresh one: the backend's CORS allowlist
// (backend/src/whattowear/main.py _CORS_ALLOWED_ORIGINS) only permits
// 3000/3100, and adding a third port is a backend change this feature's
// handoff explicitly rules out. 3100 is already claimed by the dev-server
// e2e suite (playwright.config.ts), but that suite and this one are never
// run concurrently in normal use (one drives `next dev`, this one drives a
// production build+start), so reusing the port is safe.
const PORT = 3100;

export default defineConfig({
  testDir: "./e2e-pwa",
  fullyParallel: false, // several specs mutate shared Cache Storage / the SW's own lifecycle
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  timeout: 60_000,
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  webServer: {
    command: `npm run build && npm run start -- -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
  projects: [
    {
      name: "pwa-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});

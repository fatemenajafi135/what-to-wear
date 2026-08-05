import type { NextConfig } from "next";
import withSerwistInit from "@serwist/next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Dev-only: Supabase's redirect allow-list uses 127.0.0.1 (config.toml), so
  // local OAuth testing means loading the app at http://127.0.0.1:3000. Without
  // this, Next's dev-origin protection silently blocks hydration for any host
  // other than localhost, leaving the whole app inert (no event handlers
  // attach — forms fall back to native submission, client-only state like the
  // Google button's availability check never runs).
  allowedDevOrigins: ["127.0.0.1"],
};

// Serwist is disabled in development on purpose (research.md R9): HMR and an
// unstable module graph are fundamentally incompatible with a precache
// manifest. Every service-worker behavior in this feature is only verifiable
// against a production build (`npm run build && npm run start`), never
// `next dev` — see specs/014-offline-and-updates/quickstart.md.
const withSerwist = withSerwistInit({
  swSrc: "app/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",
});

export default withSerwist(nextConfig);

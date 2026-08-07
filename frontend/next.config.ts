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
  // `withSerwistInit` below injects a webpack() function unconditionally
  // (even though `disable` makes it a no-op in development) — Next 16
  // defaults `next dev` to Turbopack and refuses to start at all when any
  // webpack config is present without an explicit turbopack acknowledgment.
  // An empty object is Next's own documented escape hatch: dev still runs
  // on Turbopack (fast, unaffected — Serwist never touches it), only the
  // startup guard is satisfied. Production (`next build --webpack`) is
  // unaffected by this and still runs webpack for real, since that's the
  // only compiler `@serwist/next`'s injectManifest plugin hooks into.
  turbopack: {},
};

// Serwist is disabled in development on purpose (research.md R9): HMR and an
// unstable module graph are fundamentally incompatible with a precache
// manifest. Every service-worker behavior in this feature is only verifiable
// against a production build (`npm run build && npm run start`), never
// `next dev` — see specs/014-offline-and-updates/quickstart.md.
const serwistEnabled = process.env.NODE_ENV !== "development";

// Defect found in review (docs/design-decisions.md §52): `app/sw.ts` reads
// `new URL(process.env.NEXT_PUBLIC_API_URL!).origin` at module top level.
// When either var is absent at build time, webpack leaves the reference
// unresolved instead of inlining a value, and the worker throws
// `TypeError: Invalid URL` the moment the browser evaluates it —
// registration fails silently, zero caches are ever created, and the whole
// feature is absent. Crucially, `next build` itself still exits 0: nothing
// about that failure happens at build time, only at script-evaluation time
// in a browser. A missing env var must fail the BUILD, loudly, here — not
// produce a service worker that looks fine until a user goes offline. Do
// NOT make `app/sw.ts` tolerate a missing value instead: a worker that runs
// with the wrong origins is worse than one that refuses to build.
if (serwistEnabled) {
  const required = ["NEXT_PUBLIC_API_URL", "NEXT_PUBLIC_SUPABASE_URL"] as const;
  const missing = required.filter((name) => !process.env[name]);
  if (missing.length > 0) {
    throw new Error(
      `Cannot build the service worker (app/sw.ts) without ${missing.join(", ")} — ` +
        `it reads these at module load to compute the API/Storage origins its cache ` +
        `routes match against. Set ${missing.length > 1 ? "them" : "it"} in frontend/.env.local ` +
        `(or the build environment's env vars) before building. See docs/design-decisions.md §52.`,
    );
  }
}

const withSerwist = withSerwistInit({
  swSrc: "app/sw.ts",
  swDest: "public/sw.js",
  disable: !serwistEnabled,
});

export default withSerwist(nextConfig);

import type { NextConfig } from "next";

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

export default nextConfig;

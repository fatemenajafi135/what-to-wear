import { createBrowserClient } from "@supabase/ssr";

/**
 * Browser Supabase client — cookie-based session (readable by middleware,
 * see lib/supabase/middleware.ts), `flowType: 'pkce'` per
 * docs/design-decisions.md §12. Create a new instance per call site rather
 * than a module-level singleton, matching @supabase/ssr's own guidance for
 * SSR frameworks.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { auth: { flowType: "pkce" } },
  );
}

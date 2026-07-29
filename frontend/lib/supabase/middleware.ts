import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Refreshes the session on every request that reaches middleware.ts,
 * rotating the refresh token (`enable_refresh_token_rotation = true` in
 * infra/supabase/config.toml) so a signed-in session survives a reload
 * without the client ever seeing an expired access token (FR-009). Returns
 * the response middleware.ts should continue with, plus the resolved user
 * for its redirect decision — `getUser()` (not `getSession()`) actually
 * revalidates the token against Supabase Auth rather than trusting a
 * possibly-stale cookie.
 */
export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!, {
    auth: { flowType: "pkce" },
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
      },
    },
  });

  const {
    data: { user },
  } = await supabase.auth.getUser();

  return { response, user };
}

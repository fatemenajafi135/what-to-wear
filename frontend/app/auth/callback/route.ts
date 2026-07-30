import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * spec.md US4 (FR-004). App-owned OAuth return route — never a
 * Supabase-hosted page (design-decisions §12's PKCE requirement 2).
 * `code` is missing or exchange fails on a cancelled/failed consent; either
 * way this must land signed-out on /signin rather than a broken
 * authenticated state, never inside the app (spec.md Edge Cases).
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}/recommend`);
    }
  }

  return NextResponse.redirect(`${origin}/signin`);
}

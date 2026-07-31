import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * specs/012-calendar/research.md §1/§3. App-owned OAuth return route for
 * the calendar connect flow — deliberately distinct from
 * app/auth/callback/route.ts, since this completes a calendar connection
 * (via this app's own backend), not a Supabase sign-in session.
 *
 * Redirects to /calendar regardless of outcome — a missing code/state or a
 * failed exchange leaves the user on the disconnected card rather than a
 * broken partial connection (spec.md User Story 1, acceptance scenario 5).
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const state = searchParams.get("state");

  if (code && state) {
    const supabase = await createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (session?.access_token) {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/calendar/connect/finish`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ code, state }),
      });
    }
  }

  return NextResponse.redirect(`${origin}/calendar`);
}

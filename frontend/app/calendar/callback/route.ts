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
 *
 * Every failure path is logged and flagged in the redirect. The first version
 * awaited the exchange without inspecting it and skipped it entirely when the
 * session was null, so a failed connect was indistinguishable from a
 * successful one: same redirect, same disconnected card, nothing in any log.
 * Whatever goes wrong next, it should be visible.
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const providerError = searchParams.get("error");

  const back = (reason?: string) =>
    NextResponse.redirect(reason ? `${origin}/calendar?connect_error=${reason}` : `${origin}/calendar`);

  // The user declined consent, or Google rejected the request outright.
  if (providerError) {
    console.warn(`[calendar/callback] provider returned error=${providerError}`);
    return back(providerError === "access_denied" ? "declined" : "provider");
  }

  if (!code || !state) {
    console.warn("[calendar/callback] missing code or state on the return URL");
    return back("invalid_response");
  }

  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    // Reachable if this route ever stops being exempted from proxy.ts's
    // session refresh — see the comment there.
    console.error("[calendar/callback] no Supabase session; cannot complete the exchange");
    return back("not_signed_in");
  }

  try {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/calendar/connect/finish`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({ code, state }),
    });

    if (!response.ok) {
      console.error(`[calendar/callback] connect/finish returned ${response.status}: ${await response.text()}`);
      return back("exchange_failed");
    }
  } catch (cause) {
    console.error("[calendar/callback] connect/finish could not be reached", cause);
    return back("unreachable");
  }

  return back();
}

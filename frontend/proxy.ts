import { NextResponse, type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

/**
 * Route protection (spec.md FR-010/FR-011/FR-012). Runs before any page
 * renders, so a signed-out visitor never sees a flash of authenticated
 * content and vice versa (SC-002/SC-003) — a per-page redirect() couldn't
 * guarantee that.
 *
 * Named `proxy.ts` per this Next.js version's current file convention (the
 * `middleware.ts` name is deprecated as of Next 16 — same request
 * lifecycle, new file/export name).
 *
 * `/` is handled by app/page.tsx itself (T025), not here — it needs to pick
 * a destination rather than just allow/deny, so it's simpler as a plain
 * Server Component redirect using the same session check.
 *
 * `/reset-password/:token` is deliberately NOT in AUTH_STACK_PREFIXES's
 * signed-in redirect: verifyOtp (ResetPasswordForm) briefly establishes its
 * own recovery session, and a visitor who already has an ordinary session in
 * the same browser must still be able to complete the flow rather than
 * being bounced to /recommend before the page ever runs (FR-007).
 */
const AUTH_STACK_PREFIXES = ["/signin", "/signup", "/forgot-password"];

function isAuthStackPath(pathname: string): boolean {
  return AUTH_STACK_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // The OAuth return route, the reset-password link target, and the root
  // redirect are all handled elsewhere / always pass through.
  if (pathname === "/" || pathname.startsWith("/auth/callback") || pathname.startsWith("/reset-password")) {
    return NextResponse.next();
  }

  const { response, user } = await updateSession(request);
  const signedIn = Boolean(user);

  if (!signedIn && !isAuthStackPath(pathname)) {
    return NextResponse.redirect(new URL("/signin", request.url));
  }

  if (signedIn && isAuthStackPath(pathname)) {
    return NextResponse.redirect(new URL("/recommend", request.url));
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|manifest.webmanifest|.*\\.(?:svg|png|jpg|jpeg|webp|ico)$).*)"],
};

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/**
 * Server Component / Route Handler Supabase client. `cookies()` is async in
 * this Next.js version, so this factory is async too — call it with
 * `await createClient()`. Writing cookies from a Server Component itself is
 * a no-op (Next disallows it outside a Route Handler/Server Action); session
 * refresh is instead handled by middleware.ts on every request.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!, {
    auth: { flowType: "pkce" },
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
        } catch {
          // Called from a Server Component render, where cookies() is read-only.
          // Harmless here — middleware.ts refreshes the session on every request.
        }
      },
    },
  });
}

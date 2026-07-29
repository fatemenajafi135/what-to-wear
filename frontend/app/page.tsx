import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

/**
 * spec.md FR-012 (003-auth) — replaces feature 001's unconditional
 * redirect() to /recommend, which stood in for real auth before this
 * feature existed.
 */
export default async function RootPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  redirect(user ? "/recommend" : "/signin");
}

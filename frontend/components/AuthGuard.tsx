"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase-client";
import { AppShell } from "./AppShell";

const PUBLIC_ROUTES = ["/sign-in", "/sign-up"];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  // undefined = still checking; null = signed out; Session = signed in
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const isPublicRoute = PUBLIC_ROUTES.includes(pathname);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => setSession(newSession));
    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (session === null && !isPublicRoute) {
      router.replace("/sign-in");
    }
  }, [session, isPublicRoute, router]);

  if (isPublicRoute) {
    return <>{children}</>;
  }

  if (session === undefined) {
    return <div className="page-loading">Loading…</div>;
  }

  if (session === null) {
    // redirect is in flight (effect above) -- render nothing rather than a
    // flash of protected content
    return null;
  }

  return <AppShell user={session.user}>{children}</AppShell>;
}

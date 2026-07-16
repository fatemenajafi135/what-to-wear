"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { User } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase-client";

const NAV_LINKS = [
  { href: "/closet", label: "Closet" },
  { href: "/closet/add", label: "Add Item" },
  { href: "/suggest", label: "Suggest" },
];

export function AppShell({ user, children }: { user: User; children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.push("/sign-in");
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-brand">What to Wear</span>
        <nav className="app-nav">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={pathname === link.href ? "app-nav-link active" : "app-nav-link"}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="app-user">
          <span className="app-user-email">{user.email}</span>
          <button type="button" onClick={handleSignOut} className="app-signout-btn">
            Sign out
          </button>
        </div>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}

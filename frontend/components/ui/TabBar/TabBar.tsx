"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles, Shirt, LayoutGrid, User, type LucideIcon } from "lucide-react";
import { NAV_DESTINATIONS, type NavId } from "@/lib/nav";
import { AvatarInitial } from "@/components/ui/AvatarInitial/AvatarInitial";
import { CreateLauncher } from "@/components/shell/CreateLauncher";
import styles from "./TabBar.module.css";

const NAV_ICONS: Record<NavId, LucideIcon> = {
  recommend: Sparkles,
  closet: Shirt,
  outfits: LayoutGrid,
  profile: User,
};

/** Stub — no auth exists in this slice, so no real user initial is available yet. */
const STUB_USER_INITIAL = "U";

function activeIdFromPathname(pathname: string): NavId | undefined {
  return NAV_DESTINATIONS.find(
    (d) => pathname === d.href || pathname.startsWith(`${d.href}/`),
  )?.id;
}

function NavItem({
  id,
  href,
  label,
  active,
  showLabel = true,
}: {
  id: NavId;
  href: string;
  label: string;
  active: boolean;
  showLabel?: boolean;
}) {
  const Icon = NAV_ICONS[id];
  return (
    <Link
      href={href}
      className={styles.item}
      aria-current={active ? "page" : undefined}
      aria-label={showLabel ? undefined : label}
    >
      <Icon size={22} strokeWidth={2} fill={active ? "currentColor" : "none"} aria-hidden="true" />
      {showLabel && <span className={styles.itemLabel}>{label}</span>}
    </Link>
  );
}

/**
 * design/design-system.md §3 TabBar + §5's responsive nav mapping. Three
 * CSS-toggled sibling markups (bar/rail/sidebar) — identical destinations at
 * every tier (Principle IX), only the chrome's presentation changes. Create
 * is composed in here at its per-tier position since that position is part
 * of each markup's layout, not a free-floating sibling.
 */
export function TabBar() {
  const pathname = usePathname();
  const activeId = activeIdFromPathname(pathname);

  const [recommend, closet, outfits, profile] = NAV_DESTINATIONS;

  return (
    <nav className={styles.nav} role="navigation" aria-label="Primary">
      {/* Mobile: bottom bar, 0-767px */}
      <div className={styles.bar} data-testid="tabbar-bar">
        <NavItem id={recommend.id} href={recommend.href} label={recommend.label} active={activeId === recommend.id} />
        <NavItem id={closet.id} href={closet.href} label={closet.label} active={activeId === closet.id} />
        <div className={styles.barCreate}>
          <CreateLauncher tier="mobile" />
        </div>
        <NavItem id={outfits.id} href={outfits.href} label={outfits.label} active={activeId === outfits.id} />
        <NavItem id={profile.id} href={profile.href} label={profile.label} active={activeId === profile.id} />
      </div>

      {/* Tablet: 76px icon rail, 768-1023px */}
      <div className={styles.rail} data-testid="tabbar-rail">
        <div className={styles.railCreateWrap}>
          <CreateLauncher tier="tablet" />
        </div>
        {NAV_DESTINATIONS.map((d) => (
          <NavItem key={d.id} id={d.id} href={d.href} label={d.label} active={activeId === d.id} showLabel={false} />
        ))}
      </div>

      {/* Desktop: 240px sidebar, 1024px+ */}
      <div className={styles.sidebar} data-testid="tabbar-sidebar">
        <div className={styles.sidebarCreateWrap}>
          <CreateLauncher tier="desktop" />
        </div>
        <NavItem id={recommend.id} href={recommend.href} label={recommend.label} active={activeId === recommend.id} />
        <NavItem id={closet.id} href={closet.href} label={closet.label} active={activeId === closet.id} />
        <NavItem id={outfits.id} href={outfits.href} label={outfits.label} active={activeId === outfits.id} />
        <Link
          href={profile.href}
          className={`${styles.item} ${styles.sidebarProfile}`}
          aria-current={activeId === profile.id ? "page" : undefined}
        >
          <AvatarInitial initial={STUB_USER_INITIAL} size={32} />
          <span className={styles.itemLabel}>{profile.label}</span>
        </Link>
      </div>
    </nav>
  );
}

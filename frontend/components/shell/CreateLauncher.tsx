import Link from "next/link";
import { Plus } from "lucide-react";
import styles from "./CreateLauncher.module.css";

export interface CreateLauncherProps {
  tier: "mobile" | "tablet" | "desktop";
  href?: string;
}

/**
 * The Create action per design/design-system.md §5's nav-mapping table — an
 * overlay launcher, never a nav destination (spec.md FR-003), so it never
 * receives `aria-current` and is never included in NAV_DESTINATIONS.
 * Position/shape differs per tier: floating FAB (mobile), circular icon
 * button pinned above the rail (tablet), full-width labelled pill pinned
 * below the wordmark (desktop) — TabBar places this within each markup.
 */
export function CreateLauncher({ tier, href = "/add" }: CreateLauncherProps) {
  if (tier === "desktop") {
    return (
      <Link href={href} className={styles.sidebarPill}>
        <Plus size={18} strokeWidth={2.2} aria-hidden="true" />
        New item
      </Link>
    );
  }

  const className = tier === "mobile" ? styles.fab : styles.railButton;
  const iconSize = tier === "mobile" ? 24 : 20;

  return (
    <Link href={href} className={className} aria-label="Add item">
      <Plus size={iconSize} strokeWidth={2.2} aria-hidden="true" />
    </Link>
  );
}

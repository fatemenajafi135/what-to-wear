"use client";

import { TabBar } from "@/components/ui/TabBar/TabBar";
import { Banner } from "@/components/ui/Banner/Banner";
import { FocusOnNavigate } from "@/components/shell/FocusOnNavigate";
import { useOnlineStatus } from "@/lib/useOnlineStatus";
import styles from "./layout.module.css";

/**
 * The authenticated shell — persists across navigation between the four
 * primary destinations. Chrome (TabBar) is CSS-only responsive per
 * design-system.md §5; Create is composed inside TabBar at its per-tier
 * position (spec.md FR-003).
 *
 * The global offline banner (design-system.md §6: "offline is a global,
 * persistent condition... can be visible at the same time as any screen
 * underneath it") lives here rather than per-screen — feature 012 is the
 * first screen needing it, but it belongs to the shell, not to Calendar.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const isOnline = useOnlineStatus();

  return (
    <>
      <TabBar />
      <FocusOnNavigate />
      {!isOnline && (
        <div className={styles.offlineBanner}>
          <Banner variant="offline">
            You&apos;re offline. Some actions are unavailable until you&apos;re reconnected.
          </Banner>
        </div>
      )}
      <main role="main" className={styles.content}>
        {children}
      </main>
    </>
  );
}
